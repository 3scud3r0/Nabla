"""Optional adapters tested against actual installed scientific libraries."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from nablamath.calc.receipt import verify_receipt
from nablamath.data.distributed_dataframe import DistributedDataFrame
from nablamath.hpc.mpi_cluster import MPICluster


def test_partitioned_frame_order_provenance_and_failures():
    source = [{'x':i,'y':i*2} for i in range(10)]
    frame = DistributedDataFrame.from_rows(source,partition_size=3)
    source[0]['x'] = 999
    with ThreadPoolExecutor(max_workers=3) as executor:
        doubled = frame.map_partitions(lambda part:[{'x':row['x']*2,'y':row['y']} for row in part],
                                       operation='double_x',executor=executor)
    assert [r['x'] for r in doubled.collect()] == list(range(0,20,2))
    assert doubled.sum('x')['result'] == 90
    assert doubled.provenance['parents'] == [frame.provenance['content_id']]
    assert verify_receipt(doubled.provenance)
    assert doubled.select('y').collect() == [{'y':i*2} for i in range(10)]
    with pytest.raises(ValueError):
        DistributedDataFrame([[{'x':1},{'y':1}]])
    def broken(part):
        raise ValueError('worker failed')
    with pytest.raises(ValueError,match='worker failed'):
        frame.map_partitions(broken,operation='broken')


def test_frame_provenance_cannot_be_rebound_or_mutated():
    from nablamath.calc.receipt import receipt
    source = receipt('source',{},[[{'x':1}]])
    frame = DistributedDataFrame([[{'x':1}]],provenance=source)
    source['result'][0][0]['x'] = 2
    assert frame.provenance['result'] == [[{'x':1}]]
    with pytest.raises(ValueError):
        DistributedDataFrame([[{'x':9}]],provenance=frame.provenance)


class SerialCommunicator:
    def Get_rank(self): return 0
    def Get_size(self): return 1
    def bcast(self,value,root): return value
    def scatter(self,value,root): return value[0]
    def allgather(self,value): return [value]
    def gather(self,value,root): return [value]


def test_collective_receipts_order_and_error_propagation():
    cluster = MPICluster(SerialCommunicator())
    result = cluster.map(lambda x:x*x,[3,1,2],operation='square')
    assert result['result'] == [9,1,4] and verify_receipt(result)
    assert len(result['metadata']['worker_receipts']) == 1
    with pytest.raises(RuntimeError,match='worker failure'):
        cluster.map(lambda x:1/0,[1],operation='fail')
    with pytest.raises(RuntimeError,match='setup failed'):
        cluster.map(lambda x:x,None,operation='fail')


def test_real_two_rank_mpi_collectives(tmp_path):
    pytest.importorskip('mpi4py')
    adjacent = Path(sys.executable).with_name('mpiexec')
    launcher = str(adjacent) if adjacent.is_file() else shutil.which('mpiexec')
    if not launcher:
        pytest.skip('MPI launcher unavailable')
    script = tmp_path/'mpi_case.py'
    script.write_text('''import json
from nablamath.hpc.mpi_cluster import MPICluster
from nablamath.calc.receipt import verify_receipt
c = MPICluster()
r = c.map(abs, [-3, 1, -2, 0] if c.comm.Get_rank() == 0 else None, operation='abs')
if r is not None:
    assert r['result'] == [3,1,2,0] and verify_receipt(r)
    assert len(r['metadata']['worker_receipts']) == 2
def bad(x):
    if x == 1: raise ValueError('rank failure')
    return x
try:
    c.map(bad, [0,1] if c.comm.Get_rank() == 0 else None, operation='failure')
except RuntimeError:
    pass
else:
    raise AssertionError('All ranks must observe the worker error')
if c.comm.Get_rank() == 0: print(json.dumps({'passed':True}))
''')
    result = subprocess.run([launcher,'-n','2',sys.executable,str(script)],capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert json.loads(result.stdout)['passed']


def test_pandas_zero_copy_and_tensor_copy_semantics():
    pd = pytest.importorskip('pandas'); np = pytest.importorskip('numpy')
    from nablamath.compat.pandas_bridge import to_numpy,to_tensor,from_tensor
    frame = pd.DataFrame(np.array([[1.,2.],[3.,4.]]))
    view = to_numpy(frame)
    assert not view.copied and not view.array.flags.writeable
    assert np.shares_memory(view.array,frame.to_numpy(copy=False))
    tensor = to_tensor(frame,requires_grad=True)
    assert from_tensor(tensor).to_numpy() == pytest.approx(frame.to_numpy())
    tensor.sum().backward(); assert tensor.grad == [[1.,1.],[1.,1.]]
    with pytest.raises(ValueError):
        to_numpy(pd.DataFrame({'a':[1],'b':[2.5]}))


def test_polars_zero_copy_and_round_trip():
    pl = pytest.importorskip('polars'); np = pytest.importorskip('numpy')
    from nablamath.compat.pandas_bridge import to_numpy,to_tensor,from_tensor
    frame = pl.DataFrame({'x':[1.,2.,3.]})
    view = to_numpy(frame)
    assert not view.copied and view.array[:,0].tolist() == [1.,2.,3.]
    assert from_tensor(to_tensor(frame),columns=['x'],library='polars').equals(frame)


def test_pytorch_trace_preserves_autograd_and_input_snapshot():
    torch = pytest.importorskip('torch')
    from nablamath.compat.pytorch_bridge import trace_execution
    records = []
    @trace_execution(sink=records.append)
    def square_sum(x):
        return (x*x).sum()
    x = torch.tensor([2.,3.],requires_grad=True)
    output = square_sum(x); output.backward()
    assert x.grad.tolist() == [4.,6.] and output.item() == 13
    assert records[0]['inputs']['args'][0]['values'] == [2.,3.]
    assert records[0]['result']['values'] == 13 and verify_receipt(records[0])
    assert any('mul' in op for op in records[0]['metadata']['operators'])


def test_xla_executes_compiled_array_on_reported_platform():
    pytest.importorskip('jax'); np = pytest.importorskip('numpy')
    from nablamath.backends.xla_compiler import XLACompiler
    compiler = XLACompiler(platform='cpu')
    record = compiler.execute(lambda x:x@x.T,np.array([[1.,2.],[3.,4.]],dtype='float32'))
    assert record['result']['values'] == [[5.,11.],[11.,25.]]
    assert record['metadata']['platform'] == 'cpu' and verify_receipt(record)


def test_cuda_real_hardware_or_explicit_unavailability():
    from nablamath.backends.cuda_dispatcher import CudaDispatcher
    from nablamath.backends import BackendUnavailable
    try:
        dispatcher = CudaDispatcher()
    except BackendUnavailable:
        pytest.skip('CuPy or real CUDA device unavailable; no GPU execution claimed')
    assert dispatcher.matmul([[1,2]],[[3],[4]])['result'] == [[11.]]
    assert dispatcher.diffuse([0,1,0],ratio=.25,steps=1)['result'] == [0,.5,0]


def test_jupyter_catalog_and_trusted_cell_magic():
    pytest.importorskip('IPython')
    from IPython.core.interactiveshell import InteractiveShell
    path = Path(__file__).resolve().parents[1]/'plugins/jupyter_nabla/magic.py'
    spec = importlib.util.spec_from_file_location('nabla_magic',path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    shell = InteractiveShell()
    module.load_ipython_extension(shell)
    record = shell.run_line_magic('nabla','beta_binomial {"successes": 2, "trials": 3}')
    assert record['result']['mean'] == '3/5'
    shell.user_ns['x'] = 3
    traced = shell.run_cell_magic('nabla_trace','x y','y = x*x\nx = 4')
    assert traced['inputs']['variables'] == {'x':3}
    assert traced['result']['variables'] == {'x':4,'y':9} and verify_receipt(traced)
    assert len(shell.user_ns['_nabla_receipts']) == 2
    with pytest.raises(ValueError):
        shell.run_cell_magic('nabla_trace','','raise ValueError("failed cell")')
    assert len(shell.user_ns['_nabla_receipts']) == 2
    module.unload_ipython_extension(shell)
