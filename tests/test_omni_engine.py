"""Numerical invariants, exact evidence, optional backends and catalog integration."""
import asyncio
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from nablamath.calc.receipt import receipt, verify_receipt
from nablamath.calc.session import CalculationSession
from nablamath.superintelligence import omni_engine as o


def test_stdlib_only_import_and_exact_dispatch():
    script = '''
from nablamath.superintelligence.omni_engine import OmniEngine, AVAILABLE, NeuralOperatorModule
from nablamath.calc.receipt import verify_receipt
assert not any(AVAILABLE.values()), AVAILABLE
r=OmniEngine().execute('verify_chain_of_thought', reasoning='x+x=2*x')
assert r['result']['all_valid'] and verify_receipt(r['receipt'])
try:
    NeuralOperatorModule().train([], [])
except RuntimeError as e:
    assert 'is_available=False' in str(e)
else:
    raise AssertionError('Missing backend silently accepted')
'''
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    subprocess.run([sys.executable, '-S', '-c', script], env=env, check=True, capture_output=True, timeout=30)


def test_macro_receipt_sink_replay_and_closed_actions():
    observed = []
    with CalculationSession(receipt_sink=observed.append) as session:
        result = session.execute('omni_superintelligence', action='verify_chain_of_thought',
                                 parameters={'reasoning': 'x+x=2*x\nx=x\n1=2', 'seed': 7}).to_data()
        assert [row['reward'] for row in result['result']['steps']] == [1, 0, -1]
        assert verify_receipt(result)
        assert any(row.get('kind') == 'execution_observation' for row in observed)
        with pytest.raises(ValueError):
            session.execute('omni_superintelligence', action='os.system')
        with pytest.raises(ValueError):
            session.execute('omni_superintelligence', action='synthesize_synthetic_dataset', parameters={'filename': 'bad.jsonl'})
    direct = o.OmniEngine(seed=7).execute('verify_chain_of_thought', reasoning='x+x=2*x')
    assert verify_receipt(direct['receipt'])
    assert direct['receipt']['metadata']['seed'] == 7
    assert direct['receipt']['metadata']['cpu_seconds'] >= 0
    tampered = deepcopy(direct['receipt']); tampered['result']['reward'] = 100
    assert not verify_receipt(tampered)


def test_truncated_causal_distribution_differs_from_conditioning():
    from fractions import Fraction
    model = o.CausalStructuralModel(
        {'Z': [0, 1], 'X': [0, 1], 'Y': [0, 1]},
        {'X': ['Z'], 'Y': ['Z']},
        {'Z': {(): {0: '1/2', 1: '1/2'}},
         'X': {(0,): {0: 1, 1: 0}, (1,): {0: 0, 1: 1}},
         'Y': {(0,): {0: 1, 1: 0}, (1,): {0: 0, 1: 1}}})
    assert model.do_calculus('Y', {'X': 1}) == {0: Fraction(1, 2), 1: Fraction(1, 2)}
    assert model.do_calculus('X', {'X': 1}) == {0: 0, 1: 1}
    with pytest.raises(ValueError):
        o.CausalStructuralModel({'X': [0, 1]}, {'X': ['X']}, {'X': {}})
    with pytest.raises(ValueError):
        model.do_calculus('Y', {'X': 3})


def test_sparse_gp_and_acquisition_uncertainty():
    np = pytest.importorskip('numpy')
    x = np.linspace(-2, 2, 50)[:, None]; y = np.sin(x[:, 0])
    gp = o.SparseGaussianProcessSurrogate(x[::5], noise=1e-4)
    gp.partial_fit(x[:25], y[:25]); gp.partial_fit(x[25:], y[25:])
    mean, variance = gp.predict(x)
    assert np.max(np.abs(mean-y)) < .04
    assert np.min(variance) >= 0
    _, far = gp.predict([[10]])
    assert far[0] > variance.max()
    acquisition = o.ActiveAcquisitionOptimizer()
    assert np.allclose(acquisition.score([1, -1], [0, 0]), [1, 0])
    assert np.allclose(acquisition.score([1], [4], method='ucb'), [5])
    with pytest.raises(ValueError):
        acquisition.score([0], [-1])


def test_notears_reports_acyclic_output():
    np = pytest.importorskip('numpy'); pytest.importorskip('scipy')
    rng = np.random.default_rng(11)
    x = rng.normal(size=(500, 3)); x[:, 1] += 2*x[:, 0]; x[:, 2] += 1.5*x[:, 1]
    result = o.NOTEARSDiscovery().fit(x, max_iter=15)
    w = result['weights']
    assert np.all(np.diag(w) == 0)
    assert not (np.linalg.matrix_power((w != 0).astype(int), 3).trace())
    assert result['causal_identification'] is False


def test_neural_fft_and_training_are_real_and_seeded():
    torch = pytest.importorskip('torch')
    np = pytest.importorskip('numpy')
    torch.set_num_threads(1)
    layer = o.SpectralConv2d(1, 1, 2, 2, seed=5)
    x = torch.zeros((1, 1, 8, 8)); x[:, :, :, :] = 1
    output = layer(x)
    assert output.shape == x.shape and torch.isfinite(output).all()
    assert torch.allclose(output, output.mean().expand_as(output), atol=1e-6)
    x = torch.randn(1, 1, 8, 8, generator=torch.Generator().manual_seed(3), requires_grad=True)
    layer(x).square().sum().backward()
    assert x.grad.abs().sum() > 0 and layer.weights1.grad.abs().sum() > 0
    model = o.NeuralOperatorModule()
    training = model.train(np.ones((2, 1, 4, 4)), np.zeros((2, 1, 4, 4)), epochs=15, width=4, modes=2, layers=1)
    assert training['losses'][-1] < training['losses'][0]
    duplicate = o.NeuralOperatorModule().train(np.ones((2, 1, 4, 4)), np.zeros((2, 1, 4, 4)), epochs=15, width=4, modes=2, layers=1)
    assert duplicate['weights_hash'] == training['weights_hash']
    assert o.DeepONet(4, 2, 8)(torch.ones(3, 4), torch.ones(5, 2)).shape == (3, 5)


def test_numpy_fno_fallback_without_torch():
    pytest.importorskip('numpy')
    script = '''
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'torch': raise ImportError('blocked')
sys.meta_path.insert(0,Block())
import numpy as np
from nablamath.superintelligence.omni_engine import FourierNeuralOperator2D, SpectralConv2d
x=np.ones((1,1,8,8))
assert SpectralConv2d(1,2,2,2)(x).shape==(1,2,8,8)
assert FourierNeuralOperator2D(width=4,modes=2,layers=1)(x).shape==x.shape
'''
    subprocess.run([sys.executable, '-c', script], check=True, capture_output=True, timeout=30)


def test_physics_residual_ad_and_conservation_fail_closed():
    np = pytest.importorskip('numpy')
    enforcer = o.PhysicsInformedEnforcer()
    assert np.allclose(enforcer.compute_pde_residual(np.ones((3, 3, 3, 2)), 'burgers'), 0)
    with pytest.raises(RuntimeError, match='aborted'):
        enforcer.enforce_conservation_law([1, 1.1])
    assert not enforcer.enforce_conservation_law([0, 0])['violation']
    fallback = o.PhysicsInformedEnforcer(exact_fallback=lambda _: {'exact': True})
    assert fallback.enforce_conservation_law([0, 1])['exact_result'] == {'exact': True}
    extreme = fallback.enforce_conservation_law([-1e308, 1e308])
    assert extreme['violation'] and extreme['relative_drift'] == 2
    assert fallback.enforce_conservation_law([1e-308, 1e308])['relative_drift'] is None
    torch = pytest.importorskip('torch')
    coordinates = torch.tensor([[0., 1., 2.], [1., 2., 3.]], requires_grad=True)
    field = lambda c: torch.stack([c[:, 1]**2, c[:, 2]*0], -1)
    residual = enforcer.compute_pde_residual(field, 'burgers', coordinates=coordinates)
    assert torch.allclose(residual[:, 0], 2*coordinates[:, 1]**3-.02)
    with pytest.raises(ValueError):
        enforcer.compute_pde_residual(field, coordinates=coordinates)


def test_radiance_variance_exr_binary_and_integrity(tmp_path):
    np = pytest.importorskip('numpy')
    tracer = o.CertifiedSpectralPathTracer({'environment': 2., 'spheres': []}, seed=3)
    image = tracer.render(3, 2, 3)
    assert np.all(image['image'] == 2) and not image['variance'].any()
    path = tmp_path/'radiance.exr'
    with CalculationSession() as session:
        audit = tracer.export_openexr_with_receipt(image, path, session)
    assert verify_receipt(audit)
    data = path.read_bytes()
    assert struct.unpack('<II', data[:8]) == (20000630, 2)
    offset = 8; attrs = {}
    while data[offset]:
        end = data.index(b'\0', offset); name = data[offset:end].decode(); offset = end+1
        end = data.index(b'\0', offset); kind = data[offset:end].decode(); offset = end+1
        size = struct.unpack_from('<I', data, offset)[0]; offset += 4
        attrs[name] = (kind, data[offset:offset+size]); offset += size
    assert attrs['nablaReceiptSHA256'][1].decode() == audit['content_id']
    assert json.loads(attrs['nablaReceipt'][1]) == audit
    first_row = struct.unpack_from('<Q', data, offset+1)[0]
    assert struct.unpack_from('<ii', data, first_row) == (0, 3*64*4)
    floats = np.frombuffer(data, dtype='<f4', offset=first_row+8, count=3*64).reshape(64, 3)
    assert np.all(floats[:32] == 2) and np.all(floats[32:] == 0)
    with CalculationSession() as session, pytest.raises(FileExistsError):
        tracer.export_openexr_with_receipt(image, path, session)
    medium = o.VolumetricMedia(.2, .3, .1)
    assert np.allclose(medium.transmittance(2), math.exp(-1))
    assert medium.phase(.5) > 0
    volume = o.CertifiedSpectralPathTracer(media=medium).render(2, 2, 4, device='cpu')
    assert np.isfinite(volume['image'].numpy()).all()


def test_surface_path_mis_bsdf_and_variance():
    np = pytest.importorskip('numpy')
    tracer = o.CertifiedSpectralPathTracer({'environment': 1., 'spheres': [
        {'center': [0, 0, 0], 'radius': 1, 'material': {'albedo': .5, 'roughness': .8}}]}, seed=8)
    a = tracer.render(2, 2, 8); b = tracer.render(2, 2, 8)
    assert np.array_equal(a['image'], b['image'])
    assert np.isfinite(a['variance']).all() and a['variance'].max() > 0
    assert o.MicrofacetBSDF(k=3, n=.3, metallic=True).evaluate([0,0,1], [0,0,1], [0,0,1]).min() > 0


def test_gaussian_mechanics_and_differentiable_raster():
    np = pytest.importorskip('numpy')
    particle = o.Gaussian3D([0, 0, 3], [1, .5, .2], opacity=.7)
    mechanics = o.ContinuumMechanicsCoupler(yield_stress=2)
    gradient = np.array([[[1., 0, 0], [0, -.5, 0], [0, 0, 0]]])
    moved = mechanics.step([particle], [[1,0,0]], gradient, .1)[0]
    assert np.allclose(moved.position, [.1, 0, 3])
    deviator = moved.stress-np.eye(3)*np.trace(moved.stress)/3
    assert math.sqrt(1.5*np.sum(deviator**2)) <= 2+1e-10
    assert np.linalg.eigvalsh(moved.covariance).min() > 0
    raster = o.DifferentiableRasterizer()
    assert raster.render([particle], 8, 8).sum() > 0
    torch = pytest.importorskip('torch')
    positions = torch.tensor([[.1, .2, 3.]], requires_grad=True)
    colors = torch.tensor([[.3, .5, .7]], requires_grad=True)
    cov = torch.eye(3).unsqueeze(0)*.1
    image = raster.rasterize_tensors(positions, cov, colors, torch.tensor([.7]), 8, 8, focal=8)
    image.sum().backward()
    assert torch.isfinite(positions.grad).all() and positions.grad.abs().sum() > 0
    assert colors.grad.abs().sum() > 0


def test_streaming_arrow_zarr_and_merkle(tmp_path):
    np = pytest.importorskip('numpy')
    ingestor = o.TensorStreamIngestor(64)
    x = np.arange(100, dtype=np.int32)
    chunks = list(ingestor.iter_chunks(x))
    assert max(map(len, chunks)) <= 64
    assert b''.join(chunks) == x.tobytes()
    assert np.shares_memory(np.frombuffer(chunks[0], dtype=x.dtype), x)
    hasher = o.StreamingMerkleHasher()
    for chunk in chunks:
        hasher.update(chunk)
    root = hasher.finalize_root_hash()
    assert root == hasher.finalize_root_hash()
    hasher.update(b'x'); assert root != hasher.finalize_root_hash()
    with pytest.raises(ValueError):
        list(ingestor.iter_chunks(x[::2]))
    pa = pytest.importorskip('pyarrow')
    assert b''.join(ingestor.iter_chunks(pa.array(x))) == x.tobytes()
    with pytest.raises(ValueError):
        list(ingestor.iter_chunks(pa.array([1, None])))
    zarr = pytest.importorskip('zarr')
    arr = zarr.create_array(store=str(tmp_path/'data.zarr'), shape=(100,), chunks=(16,), dtype='i4')
    arr[:] = x
    assert b''.join(ingestor.iter_chunks(arr)) == x.tobytes()
    oversized = zarr.create_array(store=str(tmp_path/'oversized.zarr'), shape=(100,), chunks=(100,), dtype='i4')
    with pytest.raises(ValueError, match='budget'):
        list(ingestor.iter_chunks(oversized))


def test_mcts_domains_unification_and_refusals():
    search = o.FormalMCTSSearcher()
    assert search.search('(x+1)**2', 'x*x+2*x+1')['solved']
    assert not search.search('x/x', '1', iterations=2)['solved']
    with pytest.raises(ValueError):
        search.search('1','1', tactics=[{'operation':'omni_superintelligence','arguments':{}}])
    chainer = o.ForwardAxiomChainer()
    assert chainer.unify('?x', ('f','?x')) is None
    derived = chainer.derive([('parent','a','b'),('parent','b','c')], [
        ([('parent','?x','?y'),('parent','?y','?z')], ('ancestor','?x','?z'))])
    assert derived[0]['lemma'] == ('ancestor','a','c')
    with pytest.raises(ValueError):
        chainer.derive([('p','a')], [([('p','?x')], ('q','?y'))])
    with pytest.raises(ValueError):
        asyncio.run(search.verify_external('theorem x : True := by sorry'))


@pytest.mark.parametrize('kind', ['polynomial','matrix','factorization','quantum'])
def test_forge_rlvr_roundtrip_and_tamper_refusal(tmp_path, kind):
    item = o.InverseProblemSynthesizer(13).generate(kind)
    text = o.ChainOfThoughtBuilder().build(item['thinking_trajectory'], item['solution'])
    assert text.startswith('<thought>\nPasso 1:')
    exporter = o.FrontierRLVRExporter(batch_size=1)
    assert exporter.bundle([item])['kind'] == 'nabla_artifact_bundle'
    file = tmp_path/f'{kind}.jsonl'
    result = exporter.export(iter([item]), file)
    assert result['records'] == 1
    assert json.loads(file.read_text())['verifiable_reward_receipt'] == item['receipt']['content_id']
    bad = deepcopy(item); bad['solution'] = 'forged'
    with pytest.raises(ValueError):
        exporter.prepare(bad)
    pa = pytest.importorskip('pyarrow'); import pyarrow.parquet as pq
    path = tmp_path/f'{kind}.parquet'
    exporter.export(iter([item, item]), path)
    assert pq.read_table(path).num_rows == 2
    protected = file.read_bytes()
    with pytest.raises(FileExistsError):
        exporter.export([item], file)
    assert file.read_bytes() == protected


def test_rehashed_false_answer_and_partial_dataset_refused(tmp_path):
    item = o.InverseProblemSynthesizer(1).generate()
    forged = deepcopy(item); forged['solution'] = '999999'
    forged['receipt'] = receipt('omni_synthetic_problem', forged['receipt']['inputs'],
        {'solution': forged['solution'], 'thinking_trajectory': forged['thinking_trajectory']}, parents=forged['receipt']['parents'])
    with pytest.raises(ValueError, match='justified'):
        o.FrontierRLVRExporter().prepare(forged)
    path = tmp_path/'partial.jsonl'
    with pytest.raises(ValueError):
        o.FrontierRLVRExporter().export([item, forged], path)
    assert not path.exists()


def test_prm_dpo_counterexample_curriculum_and_cf(tmp_path):
    prm = o.ProcessRewardVerifier()
    assert not prm.verify('x/x=1')['all_valid']
    assert not prm.verify('therefore all primes are odd')['all_valid']
    prm.export_dpo('Simplifique', 'x+x=2*x', 'x+x=3*x', tmp_path/'dpo.jsonl')
    with pytest.raises(ValueError):
        prm.export_dpo('p', 'x=x', 'x=x', tmp_path/'bad.jsonl')
    fuzzer = o.CounterexampleFuzzer(1)
    assert fuzzer.fuzz(lambda v: v['x'] > 0, {'x':[0,1]})['input']['x'] == 0
    assert fuzzer.fuzz(lambda v: v['x'] >= 0, {'x':[0,1]}, 10)['status'] == 'inconclusive'
    cf = o.RamanujanEngine()
    assert cf.continued_fraction([1,1], [1,1,1]) == o.Fraction(3,2)
    with pytest.raises(ZeroDivisionError):
        cf.continued_fraction([1], [1,0])
    arena = o.SelfPlayCurriculumArena()
    initial = arena.difficulty()
    for _ in range(30): arena.update(True)
    assert arena.difficulty() > initial
    assert arena.play(lambda _: 'incorrect', rounds=1)[0]['success'] is False
    assert len(list(arena.distill_failures())) == 1


def test_structured_smt_step_and_concrete_counterexample():
    pytest.importorskip('z3')
    from nablamath.formal.statement import FormalStatement
    proven = FormalStatement.equality('x+x','2*x').to_data()
    refuted = FormalStatement.equality('x*x','x').to_data()
    result = o.ProcessRewardVerifier().verify([{'statement': proven}])
    assert result['steps'][0]['reward'] == 1
    bad = o.CounterexampleFuzzer().check_smt(refuted)
    assert bad['status'] == 'COUNTEREXAMPLE_FOUND' and bad['counterexample'] is not None


@pytest.mark.parametrize('bad', [math.nan, math.inf, -math.inf])
def test_nonfinite_inputs_fail_closed(bad):
    with pytest.raises(ValueError):
        o.OmniEngine().execute('render_certified_radiance', scene={'environment': bad})
    with pytest.raises(ValueError):
        o.PhysicsInformedEnforcer(viscosity=bad)
    with pytest.raises(ValueError):
        o.SelfPlayCurriculumArena(solver_rating=bad)


def test_finite_extremes_refuse_overflow_and_underflow():
    np = pytest.importorskip('numpy')
    with np.errstate(over='ignore', invalid='ignore'):
        with pytest.raises(ValueError):
            o.SparseGaussianProcessSurrogate([[0], [1]], length_scale=1e-300)
        with pytest.raises(ValueError):
            o.VolumetricMedia(1e308, 1e308)
        tracer = o.CertifiedSpectralPathTracer({'environment': 1., 'spheres': [
            {'center': [0, 0, 0], 'radius': 1e308}]})
        with pytest.raises(ValueError, match='overflow'):
            tracer.render(1, 1, 2)
        arena = o.SelfPlayCurriculumArena(solver_rating=1.7e308, generator_rating=1.7e308, k_factor=1.7e308)
        with pytest.raises(ValueError):
            arena.update(True)
        assert math.isfinite(arena.solver_rating) and arena.rounds == 0
    result = o.CounterexampleFuzzer().fuzz(lambda v: -1e308 <= v['x'] <= 1e308, {'x': [-1e308, 1e308]}, 100)
    assert result['status'] == 'inconclusive'


def test_macro_structured_smt_is_replayable():
    pytest.importorskip('z3')
    from nablamath.formal.statement import FormalStatement
    with CalculationSession() as session:
        result = session.execute('omni_superintelligence', action='verify_chain_of_thought', parameters={
            'reasoning': [{'statement': FormalStatement.equality('x+x', '2*x').to_data()}]}).to_data()
    assert result['result']['all_valid'] and verify_receipt(result)


def test_ai_action_schema_is_closed_before_backend_execution():
    jsonschema = pytest.importorskip('jsonschema')
    from nablamath.ai.tool_schemas import schema_for
    from nablamath.calc.catalog import catalog
    operation = next(row for row in catalog()['operations'] if row['name'] == 'omni_superintelligence')
    schema = schema_for(operation)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate({'action': 'verify_chain_of_thought', 'parameters': {'reasoning': 'x+x=2*x'}})
    for bad in [
        {'action': 'os.system', 'parameters': {}},
        {'action': 'train_surrogate_fno', 'parameters': {'inputs': {'code': 'execute'}, 'targets': [0]}},
        {'action': 'render_certified_radiance', 'parameters': {'scene': {'spheres': [{'center': [0, 0, 0], 'radius': 1, 'code': 'execute'}]}}},
        {'action': 'synthesize_synthetic_dataset', 'parameters': {'filename': 'external.jsonl'}},
    ]:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(bad)


def test_rehashed_unrelated_prompt_cannot_claim_calculation():
    item = o.InverseProblemSynthesizer(1).generate()
    item['prompt'] = 'Prove an unrelated universal conjecture.'
    old = item['receipt']
    item['receipt'] = receipt('omni_synthetic_problem', {**old['inputs'], 'prompt': item['prompt']}, old['result'], parents=old['parents'])
    with pytest.raises(ValueError, match='justified'):
        o.FrontierRLVRExporter().prepare(item)
