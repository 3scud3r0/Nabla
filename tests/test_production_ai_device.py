"""Hard process deadlines, precise tool schemas and explicit device recovery."""
import multiprocessing
import time
import asyncio
import json
import sys
import pytest

from nablamath.ai.sandbox_verifier import AIVerifier,VerificationStatus
from nablamath.ai.agent_tools import AgentTools,tool_schemas


def _stalled_solver(connection,*args):
    time.sleep(30)


def test_conjecture_proof_counterexample_domain_and_inconsistent_hypotheses():
    pytest.importorskip('z3')
    verifier = AIVerifier()
    assert verifier.verify('x*x >= 0').status == VerificationStatus.PROVEN
    assert verifier.verify('x/x = 1').status == VerificationStatus.PROVEN
    disproved = verifier.verify('x+1 = x')
    assert disproved.status == VerificationStatus.COUNTEREXAMPLE_FOUND
    assert disproved.counterexample == {'x':'0'} and disproved.details['exact_replay']
    rejected = verifier.verify({'goal':'x > 0','assumptions':['x < 0','x > 0']})
    assert rejected.status == VerificationStatus.REJECTED
    assert verifier.verify('__import__("os") = 0').status != VerificationStatus.PROVEN


def test_solver_translation_or_native_hang_is_killed_by_total_wall_deadline(monkeypatch):
    import nablamath.ai.sandbox_verifier as module
    monkeypatch.setattr(module,'verify_worker',_stalled_solver)
    before = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    result = module.AIVerifier(timeout_seconds=.4).verify('x = x')
    elapsed = time.monotonic()-started
    assert result.status == VerificationStatus.TIMEOUT_REJECTED
    assert elapsed < .65
    assert {p.pid for p in multiprocessing.active_children()} <= before


def test_schema_rejects_nested_nonnumeric_matrix_before_starting_math(monkeypatch):
    jsonschema = pytest.importorskip('jsonschema')
    tools = AgentTools()
    def unexpected(*args,**kwargs):
        raise AssertionError('Math must not start for an invalid matrix')
    monkeypatch.setattr(tools.registry,'execute',unexpected)
    with pytest.raises(jsonschema.ValidationError):
        tools.call('solve_linear',{'matrix':[[1,{'code':'arbitrary'}]],'rhs':[1]})
    assert tools.calls == 0
    schemas = {tool['name']:tool['inputSchema'] for tool in tool_schemas()}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'kind':'mobius','points':[[1,0]]},schemas['complex_analysis'])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'nodes':[{'op':'eval','source':'print(1)'}],'inputs':{'x':1},'output':0},schemas['autograd'])


def test_tool_concurrency_cap_fails_before_starting_another_process():
    pytest.importorskip('jsonschema')
    tools = AgentTools(max_concurrent=1)
    assert tools._capacity.acquire(blocking=False)
    try:
        with pytest.raises(RuntimeError,match='capacity'):
            tools.call('binomial',{'n':5,'k':2})
    finally:
        tools._capacity.release()
    assert tools.calls == 0


def test_conjecture_tool_respects_smaller_client_time_and_output_budgets(monkeypatch):
    from nablamath.agents.permissions import Permissions
    from nablamath.ai.sandbox_verifier import VerificationResult
    import nablamath.ai.sandbox_verifier as module
    configured = []
    class FakeVerifier:
        def __init__(self,*,timeout_seconds=5):
            configured.append(timeout_seconds)
        def verify(self,arguments):
            return VerificationResult(VerificationStatus.REJECTED,{'reason':'x'*300},0)
    monkeypatch.setattr(module,'AIVerifier',FakeVerifier)
    tools = AgentTools(Permissions(frozenset({'verify_conjecture'}),max_calls=1,
                                  timeout_seconds=.2,max_output_bytes=128))
    with pytest.raises(ValueError,match='output byte budget'):
        tools.verify_conjecture({'goal':'x = x'})
    assert configured == [.2] and tools.calls == 1


def test_cpu_numerical_backend_retains_native_gradients_and_matches_exact_oracle():
    torch = pytest.importorskip('torch')
    from nablamath.backends.cuda_dispatcher import CudaDispatcher
    dispatcher = CudaDispatcher(backend='torch',require_cuda=False)
    left = torch.tensor([[1.,2.],[3.,4.]],requires_grad=True)
    right = torch.tensor([[5.],[6.]],requires_grad=True)
    result = dispatcher.execute('matmul',left=left,right=right)
    result.result.sum().backward()
    assert left.grad.tolist() == [[5,6],[5,6]] and right.grad.tolist() == [[4],[6]]
    assert result.to_data()['metadata']['platform'] == 'cpu'
    assert result.to_data()['metadata']['capture'] == 'metadata_only'
    fitted = dispatcher.execute('least_squares',predictors=[[0],[1],[2]],response=[1,3,5],capture_values=True)
    assert fitted.to_data()['result']['coefficients'] == pytest.approx([1,2],abs=1e-12)
    ode = dispatcher.execute('ode_solve',model='exponential_decay',initial=[1.],steps=100,capture_values=True)
    import math
    assert ode.to_data()['result']['final'] == pytest.approx([math.exp(-1)],abs=1e-9)


def test_cuda_oom_fault_injection_retries_cpu_and_records_actual_backend(monkeypatch):
    torch = pytest.importorskip('torch')
    from nablamath.backends.cuda_dispatcher import CudaDispatcher
    dispatcher = CudaDispatcher(backend='torch',require_cuda=False)
    dispatcher.platform = 'cuda'
    original = dispatcher._run; platforms = []
    def allocation_failure(backend,platform,operation,arguments):
        platforms.append(platform)
        if platform == 'cuda':
            raise torch.OutOfMemoryError('injected VRAM exhaustion')
        return original(backend,platform,operation,arguments)
    monkeypatch.setattr(dispatcher,'_run',allocation_failure)
    result = dispatcher.execute('matmul',left=[[1,2]],right=[[3],[4]],capture_values=True)
    assert platforms == ['cuda','cpu'] and result.to_data()['result'] == [[11]]
    assert result.device == 'cpu' and 'OutOfMemoryError' in result.fallback_reason
    dispatcher.allow_cpu_fallback = False
    with pytest.raises(torch.OutOfMemoryError):
        dispatcher.execute('matmul',left=[[1]],right=[[2]])


def test_invalid_math_does_not_trigger_fallback():
    pytest.importorskip('torch')
    from nablamath.backends.cuda_dispatcher import CudaDispatcher
    dispatcher = CudaDispatcher(backend='torch',require_cuda=False)
    with pytest.raises(ValueError,match='full column rank'):
        dispatcher.execute('least_squares',predictors=[[1],[1],[1]],response=[1,2,3])


def test_actual_cuda_device_and_numerical_algorithms():
    torch = pytest.importorskip('torch')
    if not torch.cuda.is_available():
        pytest.skip('Actual NVIDIA hardware is required; OOM injection is a separate test')
    import math
    from nablamath.backends.cuda_dispatcher import CudaDispatcher
    dispatcher = CudaDispatcher(backend='torch')
    native = torch.tensor([[1.,2.]],device='cuda',requires_grad=True)
    result = dispatcher.execute('matmul',left=native,right=native.T)
    assert result.result.is_cuda
    result.result.sum().backward()
    assert native.grad.cpu().tolist() == [[2,4]]
    fit = dispatcher.execute('least_squares',predictors=[[0],[1],[2]],response=[1,3,5],capture_values=True)
    assert fit.to_data()['result']['coefficients'] == pytest.approx([1,2],abs=1e-10)
    ode = dispatcher.execute('ode_solve',model='exponential_decay',initial=[1.],steps=100,capture_values=True)
    assert ode.to_data()['result']['final'] == pytest.approx([math.exp(-1)],abs=1e-9)
    assert dispatcher.diffuse([0,1,0],ratio=.25,steps=2)['result'] == pytest.approx([0,.25,0])


def test_actual_mcp_verifier_and_structured_receipt_roundtrip():
    pytest.importorskip('mcp'); pytest.importorskip('jsonschema'); pytest.importorskip('z3')
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from nablamath.calc.receipt import verify_receipt
    async def exercise():
        parameters = StdioServerParameters(command=sys.executable,
            args=['-m','nablamath.ai.mcp_server','--verify-claims'])
        async with stdio_client(parameters) as (read,write):
            async with ClientSession(read,write) as client:
                await client.initialize()
                listed = await client.list_tools()
                assert len(listed.tools) == len(tool_schemas())+1
                result = await client.call_tool('verify_conjecture',{'goal':'x*x >= 0'})
                assert not result.isError
                record = json.loads(result.structuredContent['audit_receipt'])
                assert verify_receipt(record) and record['result']['status'] == 'PROVEN'
                assert result.structuredContent['content_id'] == record['content_id']
                invalid = await client.call_tool('solve_linear',{'matrix':[['bad']],'rhs':[1]})
                assert invalid.isError
    asyncio.run(exercise())


def test_accelerated_session_uses_background_sink_without_materialising_tensors(monkeypatch):
    torch = pytest.importorskip('torch')
    from nablamath.calc import CalculationSession
    from nablamath.backends.cuda_dispatcher import CudaDispatcher
    dispatcher = CudaDispatcher(backend='torch',require_cuda=False)
    records = []
    native = torch.ones((2,2),requires_grad=True)
    def forbidden(*args,**kwargs):
        raise AssertionError('Metadata dispatch must not copy tensor contents')
    with monkeypatch.context() as patch:
        for method in ('cpu','numpy','tolist','item'):
            patch.setattr(torch.Tensor,method,forbidden)
        with CalculationSession(background_receipts=True,receipt_sink=records.append) as session:
            result = session.execute_accelerated('matmul',dispatcher=dispatcher,left=native,right=native)
            result.result.sum().backward()
    assert len(records) == 1 and records[0]['metadata']['capture'] == 'metadata_only'
    assert result.to_data() == records[0] and native.grad.tolist() == [[4,4],[4,4]]
