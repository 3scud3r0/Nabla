"""Bounded background auditing and native tensor interception without readback."""
from concurrent.futures import Future
import gc
from threading import Event,Thread
import weakref

import pytest
from nablamath.calc import CalculationSession
from nablamath.calc.receipt import verify_receipt


def test_background_result_and_receipt_match_synchronous_and_freeze_inputs():
    arguments = {'kind':'add','values':[[1,2]],'other':[[3,4]]}
    expected = CalculationSession().execute('tensor',**arguments).to_data()
    records = []
    with CalculationSession(background_receipts=True,receipt_sink=records.append) as session:
        pending = session.execute('tensor',**arguments)
        assert pending.result['values'] == [[4,6]]
        detached = pending.result; detached['values'][0][0] = 900
        arguments['values'][0][0] = 800
    assert pending.done() and pending.to_data() == expected
    assert records == [expected] and verify_receipt(records[0])


def test_background_buffer_backpressure_sink_failure_and_closed_session():
    gate = Event(); started = Event()
    def blocked_sink(record):
        started.set(); assert gate.wait(5)
    session = CalculationSession(background_receipts=True,max_pending=1,receipt_sink=blocked_sink)
    pending = session.execute('binomial',n=5,k=2)
    assert started.wait(2)
    try:
        with pytest.raises(BufferError):
            session.execute('binomial',n=6,k=2)
    finally:
        gate.set(); session.close()
    assert pending.to_data()['result']['value'] == 10
    with pytest.raises(RuntimeError,match='closed'):
        session.execute('binomial',n=5,k=2)
    def failed_sink(record):
        raise OSError('audit disk is full')
    session = CalculationSession(receipt_sink=failed_sink)
    future = session.record_observation('native',{},1)
    with pytest.raises(OSError,match='disk is full'):
        session.flush()
    with pytest.raises(OSError):
        future.result()
    session.close()


def test_completed_background_futures_are_not_retained():
    with CalculationSession(background_receipts=True,max_pending=8) as session:
        for _ in range(1000):
            pending = session.execute('binomial',n=5,k=2)
            assert pending.to_data()['result']['value'] == 10
        session.flush()
        assert not session._pending


def test_native_dispatch_forbids_all_cpu_materialisation_and_preserves_alias_gradients(monkeypatch):
    torch = pytest.importorskip('torch')
    from nablamath.compat.pytorch_bridge import TorchTrace
    x = torch.tensor([[1.,2.],[3.,4.]],requires_grad=True)
    records = []
    def forbidden(*args,**kwargs):
        raise AssertionError('A tensor was materialised on the CPU')
    with monkeypatch.context() as patch:
        for method in ('cpu','numpy','tolist','item'):
            patch.setattr(torch.Tensor,method,forbidden)
        with TorchTrace(sink=records.append,batch_size=4,collect=True) as trace:
            view = x.view(4)
            y = x@x.T
            y.sum().backward()
    assert view.untyped_storage().data_ptr() == x.untyped_storage().data_ptr()
    assert x.grad.tolist() == [[8,12],[8,12]]
    assert any('mm' in event['operation'] for r in records for event in r['result'])
    assert all(r['metadata']['capture'] == 'metadata_only' and not r['metadata']['tensor_contents_hashed'] and verify_receipt(r) for r in records)
    assert trace.batch_count == len(records) and trace.receipts == records


def test_trace_does_not_hold_native_tensors_and_dlpack_shares_storage():
    torch = pytest.importorskip('torch'); np = pytest.importorskip('numpy')
    from nablamath.compat.pytorch_bridge import TorchTrace,from_dlpack
    array = np.array([1.,2.],dtype='float64')
    tensor = from_dlpack(array)
    tensor[0] = 7
    assert array[0] == 7 and tensor.data_ptr() == array.__array_interface__['data'][0]
    with TorchTrace(batch_size=2) as trace:
        temporary = tensor+1
        reference = weakref.ref(temporary)
        del temporary; gc.collect()
        assert reference() is None
    with pytest.raises(RuntimeError,match='collect=True'):
        _ = trace.receipts


def test_flush_waits_until_completed_record_releases_its_buffer_slot(monkeypatch):
    callback_entered,release_callback,release_sink,finished = Event(),Event(),Event(),Event()
    original = Future.add_done_callback
    errors = []
    def delayed_callback(future,callback):
        def wrapped(done):
            callback_entered.set()
            assert release_callback.wait(5)
            callback(done)
        return original(future,wrapped)
    monkeypatch.setattr(Future,'add_done_callback',delayed_callback)
    session = CalculationSession(background_receipts=True,max_pending=1,
                                 receipt_sink=lambda record:release_sink.wait(5))
    def flush():
        try:
            session.flush()
        except Exception as error:
            errors.append(error)
        finally:
            finished.set()
    worker = None
    try:
        session.execute('binomial',n=5,k=2)
        release_sink.set()
        assert callback_entered.wait(2)
        worker = Thread(target=flush);worker.start()
        assert not finished.wait(.1), 'flush returned while its completed record still occupied the buffer'
        release_callback.set();worker.join(timeout=2)
        assert finished.is_set() and not errors
        session.execute('binomial',n=6,k=2)
    finally:
        release_sink.set();release_callback.set()
        if worker is not None:
            worker.join(timeout=2)
        session.close()
