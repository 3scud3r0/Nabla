"""Device parity, exact stencil identities, physical limits and native receipts."""
import asyncio
from fractions import Fraction
import hashlib
import math
import os

import pytest

from nablamath.calc import CalculationSession
from nablamath.calc.receipt import verify_receipt
from nablamath.superintelligence import omni_engine as o


@pytest.fixture
def torch():
    module = pytest.importorskip('torch')
    previous = module.get_num_threads()
    module.set_num_threads(1)
    yield module
    module.set_num_threads(previous)


@pytest.fixture
def cuda(torch):
    if not torch.cuda.is_available():
        if os.environ.get('NABLA_REQUIRE_CUDA') == '1':
            pytest.fail('CUDA hardware/build is required by this validation job')
        pytest.skip('Real CUDA device unavailable; GPU execution is not claimed')
    return 'cuda:0'


def test_all_embedded_stencils_match_polynomial_moments_and_analytic_derivatives():
    np = pytest.importorskip('numpy')
    assert len(o.STENCIL_KERNELS) == 480
    for (derivative, accuracy), coefficients in o.STENCIL_MOMENTS.items():
        for degree in range(len(coefficients)):
            moment = sum(Fraction(n, d)*offset**degree for offset, n, d in coefficients)
            assert moment == (math.factorial(degree) if degree == derivative else 0)
    x = np.arange(64)*2*math.pi/64
    for (derivative, accuracy, axis, boundary), kernel in o.STENCIL_KERNELS.items():
        shape = [1]*abs(axis); shape[axis] = 64
        field = np.sin(x).reshape(shape)
        result = kernel(field, 2*math.pi/64).reshape(-1)
        expected = (np.cos(x), -np.sin(x), -np.cos(x), np.sin(x))[derivative-1]
        radius = max(abs(offset) for offset, _, _ in o.STENCIL_MOMENTS[derivative, accuracy])
        assert np.max(np.abs(result[radius:-radius]-expected[radius:-radius])) < .02


def test_torch_stencil_autograd_and_pde_device_residual(torch):
    x = torch.linspace(0, 2*math.pi, 64, dtype=torch.float64, requires_grad=True)
    derivative = o.GPUStencilBank.derivative(x.sin(), float((x[1]-x[0]).detach()), derivative=2, accuracy=6)
    derivative.square().sum().backward()
    assert x.grad is not None and torch.isfinite(x.grad).all() and x.grad.abs().sum() > 0
    velocity = torch.ones((3, 5, 5, 2), requires_grad=True)
    residual = o.PhysicsInformedEnforcer().compute_pde_residual(velocity, 'navier_stokes', pressure=torch.ones(3,5,5))
    assert residual.shape == (3,5,5,3) and residual.abs().max() < 1e-5
    residual.square().sum().backward()
    assert velocity.grad is not None


def test_train_checkpoint_physics_and_native_observation(torch, tmp_path):
    module = o.NeuralOperatorModule()
    inputs = torch.ones((4,1,8,8))
    result = module.train(inputs, inputs*0, epochs=3, width=4, modes=2, layers=1,
                          device='cpu', batch_size=2, physics_weight=.1)
    assert result['backend'] == 'torch-cpu' and len(result['physics_losses']) == 3
    assert any(p.is_complex() and p.imag.abs().sum() > 0 for p in module.model.parameters())
    saved = module.save_checkpoint(tmp_path/'model.pt')
    restored = o.NeuralOperatorModule(); restored.load_checkpoint(saved['filename'], saved['sha256'], 'cpu')
    assert torch.allclose(module.predict(inputs), restored.predict(inputs))
    with pytest.raises(ValueError, match='hash'):
        restored.load_checkpoint(saved['filename'], '0'*64, 'cpu')
    engine = o.OmniEngine(device='cpu')
    output = engine.execute('fit_sparse_gp', capture_values=False, inducing_points=torch.tensor([[0.],[1.]]),
                            inputs=torch.tensor([[0.],[1.]]), targets=torch.tensor([0.,1.]), queries=torch.tensor([[.5]]))
    assert isinstance(output['result']['mean'], torch.Tensor)
    assert verify_receipt(output['receipt'])
    record = output['receipt']['result']['mean']
    assert record['kind'] == 'native_tensor'
    assert record['sha256'] == hashlib.sha256(output['result']['mean'].numpy().tobytes()).hexdigest()
    assert output['receipt']['metadata']['gpu_seconds'] is None


def test_torch_gp_parity_acquisition_and_notears(torch):
    np = pytest.importorskip('numpy')
    x = np.linspace(-2,2,40)[:,None]; y = np.sin(x[:,0]); points = x[::4]
    host = o.SparseGaussianProcessSurrogate(points).fit(x,y)
    native = o.SparseGaussianProcessSurrogate(points, device='cpu').fit(x,y)
    hm,hv = host.predict(x); tm,tv = native.predict(torch.tensor(x))
    assert np.allclose(hm,tm.numpy(),atol=1e-7) and np.allclose(hv,tv.numpy(),atol=1e-7)
    ei = o.ActiveAcquisitionOptimizer().score(tm,tv)
    assert torch.isfinite(ei).all() and (ei >= -1e-12).all()
    result = o.NOTEARSDiscovery().fit(torch.tensor([[0.,0.],[1.,2.],[2.,4.],[3.,6.]]),
                                     device='cpu', max_iter=3, inner_steps=30)
    weights = result['weights']
    assert weights.device.type == 'cpu' and torch.isfinite(weights).all()
    assert weights[0,1] == 0 or weights[1,0] == 0
    assert result['causal_identification'] is False


def test_tensor_triangle_radiance_and_absorbing_sphere_limit(torch):
    triangle = {'vertices':[[-20,-20,0],[20,-20,0],[0,20,0]], 'emission':3,
                'material':{'albedo':0,'n':1}}
    tracer = o.CertifiedSpectralPathTracer({'environment':0, 'triangles':[triangle]}, seed=5, max_depth=2)
    result = tracer.render(2,2,4,device='cpu')
    assert torch.allclose(result['image'],torch.full_like(result['image'],3))
    assert result['variance'].max() == 0
    absorbing = o.CertifiedSpectralPathTracer({'environment':1,'medium':{'sigma_a':.4,'sigma_s':0}},seed=1,max_depth=2)
    image = absorbing.render(1,1,1024,device='cpu',medium_radius=1,camera={'origin':[0,0,0],'target':[0,0,1]})
    assert abs(float(image['image'].mean())-math.exp(-.4)) < .06
    scattering = o.CertifiedSpectralPathTracer({'environment':1,'medium':{'sigma_a':0,'sigma_s':.2,'g':.4}},seed=1,max_depth=6)
    result = scattering.render(2,2,32,device='cpu',medium_radius=1,camera={'origin':[0,0,0],'target':[0,0,1]})
    assert torch.isfinite(result['image']).all() and result['variance'].min() >= 0


def test_batched_constitutive_update_matches_numpy(torch):
    np = pytest.importorskip('numpy')
    particle = o.Gaussian3D([0,0,3],[1,.5,.2])
    coupler = o.ContinuumMechanicsCoupler(yield_stress=2)
    gradients = np.array([[[1.,0,0],[0,-.5,0],[0,0,0]]])
    expected = coupler.step([particle],[[1,0,0]],gradients,.1)[0]
    result = coupler.step_tensors(torch.tensor([[0.,0.,3.]],dtype=torch.float64),
        torch.tensor(particle.covariance[None]), torch.zeros((1,3,3),dtype=torch.float64),
        torch.tensor([[1.,0.,0.]],dtype=torch.float64),torch.tensor(gradients),.1)
    assert np.allclose(result['positions'][0].numpy(),expected.position)
    assert np.allclose(result['covariances'][0].numpy(),expected.covariance)
    assert np.allclose(result['stresses'][0].numpy(),expected.stress)


def test_horn_search_and_pinned_lean_bridge():
    search = o.FormalMCTSSearcher()
    rules = [([('p','?x')],('q','?x')),([('q','?x')],('r','?x')),([('r','?x')],('s','?x'))]
    result = search.search_horn([('p','a')],rules,[('s','a')])
    assert result['solved'] and len(result['proof']) >= 3
    assert not search.search_horn([('p','a')],rules,[('s','b')],iterations=4)['solved']
    lean = asyncio.run(search.verify_external('theorem omni_nat_identity (x : Nat) : x = x := by rfl'))
    assert lean['status'] in {'checked','unavailable'}
    if lean['status'] == 'checked':
        assert lean['verified'] and lean['exit_code'] == 0


def test_high_precision_pslq_recovers_known_e_convergent():
    pytest.importorskip('mpmath')
    denominators = [2]+[2*((i+1)//3) if i%3 == 2 else 1 for i in range(1,100)]
    result = o.RamanujanEngine().search_high_precision([1]*99,denominators,precision=80,
                                                      powers=1,max_coefficient=10,tolerance='1e-50')
    assert result['relation'] and result['numerically_stable'] and not result['proven']
    assert result['relation']['e^1'] == -result['relation']['continued_fraction']


def test_cuda_request_never_silently_falls_back(torch):
    if not torch.cuda.is_available():
        with pytest.raises(RuntimeError,match='CUDA requested'):
            o.DeviceRuntime('cuda')
        with pytest.raises(RuntimeError,match='CUDA requested'):
            o.OmniEngine(device='cuda').execute('train_surrogate_fno',inputs=[[[[1]*4]*4]],targets=[[[[0]*4]*4]],epochs=1)


def test_cuda_fno_gp_stencils_render_and_receipt(torch,cuda):
    engine = o.OmniEngine(seed=11,device=cuda)
    x = torch.ones((2,1,8,8),device=cuda)
    trained = engine.execute('train_surrogate_fno',capture_values=False,inputs=x,targets=x*0,
                            epochs=2,width=4,modes=2,layers=1,batch_size=1,physics_weight=.1)
    assert next(engine.neural.model.parameters()).is_cuda
    assert trained['receipt']['metadata']['gpu_seconds'] is not None
    assert trained['receipt']['metadata']['gpu_timing_status'] == 'cuda_events'
    gp = o.SparseGaussianProcessSurrogate([[0.],[1.]],device=cuda).fit([[0.],[1.]],[0.,1.])
    mean,var = gp.predict([[.5]])
    assert mean.is_cuda and var.is_cuda and var.min() >= 0
    field = torch.sin(torch.arange(64,device=cuda,dtype=torch.float64)*2*math.pi/64)
    derived = o.GPUStencilBank.derivative(field,2*math.pi/64,accuracy=8)
    assert derived.is_cuda
    scene={'environment':1,'spheres':[{'center':[0,0,0],'radius':1}],
           'triangles':[{'vertices':[[-2,-2,2],[2,-2,2],[0,2,2]],'emission':2}],
           'medium':{'sigma_a':.01,'sigma_s':.02,'g':.3}}
    rendered = engine.execute('render_certified_radiance',capture_values=False,scene=scene,width=4,height=4,samples=8)
    assert rendered['result']['image'].is_cuda and verify_receipt(rendered['receipt'])


def test_cuda_raster_and_constitutive_gradients(torch,cuda):
    positions=torch.tensor([[.1,.2,3.]],device=cuda,requires_grad=True)
    covariance=torch.eye(3,device=cuda).unsqueeze(0)*.1
    image=o.DifferentiableRasterizer().rasterize_tensors(positions,covariance,
            torch.ones((1,3),device=cuda),torch.tensor([.7],device=cuda),8,8)
    image.sum().backward()
    assert positions.grad.is_cuda and positions.grad.abs().sum() > 0
    updated=o.ContinuumMechanicsCoupler().step_tensors(positions,covariance,
            torch.zeros((1,3,3),device=cuda),torch.ones_like(positions),torch.zeros((1,3,3),device=cuda),.1)
    assert updated['positions'].is_cuda and updated['covariances'].is_cuda


def test_device_stream_preserves_scalars_and_rejects_dtype_mismatch(torch):
    np = pytest.importorskip('numpy')
    source = np.arange(40,dtype='float32')
    chunks = list(o.TensorStreamIngestor(32).iter_device_chunks(source,device='cpu'))
    assert torch.equal(torch.cat(chunks),torch.from_numpy(source))
    with pytest.raises(ValueError,match='dtype'):
        list(o.TensorStreamIngestor(32).iter_device_chunks(source.astype('float64'),device='cpu'))


def test_model_constructors_restore_callers_rng(torch):
    state = torch.random.get_rng_state().clone()
    o.FourierNeuralOperator2D(width=4,modes=2,layers=1,seed=42)
    assert torch.equal(state,torch.random.get_rng_state())
    o.DeepONet(4,2,8,seed=7)
    assert torch.equal(state,torch.random.get_rng_state())
