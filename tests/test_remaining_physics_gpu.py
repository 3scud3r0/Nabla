import math
import pytest
from nablamath.physics.relativity.einstein_solver import FlatFLRW
from nablamath.physics.fluids.channel import channel_velocity
from nablamath.gpu.kernels.egraph_triton import canonical_children_cpu
from nablamath.gpu.profiler import profile_operation, hardware_profile


@pytest.mark.parametrize('w', [0, 1/3, 1, -1/3, -0.8])
@pytest.mark.parametrize('t', [0.1, 1, 10])
def test_einstein_field_equations(w, t):
    model = FlatFLRW(w)
    for value in model.field_residuals(t).values():
        assert abs(value) < 1e-9


def test_radiation_trace_and_dust_scale():
    assert FlatFLRW(1/3).ricci_scalar(2) == 0
    assert FlatFLRW().scale(8) == pytest.approx(4)
    assert FlatFLRW().density(2) == pytest.approx(1/(24*math.pi))


def test_null_geodesic_and_connection_symmetry():
    model = FlatFLRW()
    gamma = model.christoffel(1)
    assert all(gamma[i][j][k] == gamma[i][k][j]
               for i in range(4) for j in range(4) for k in range(4))
    acceleration = model.geodesic_acceleration(1, (1, 1, 0, 0))
    assert acceleration == pytest.approx((-2/3, -4/3, 0, 0))
    assert model.radial_null_displacement(1, 8) == pytest.approx(3)
    assert model.radial_null_displacement(1, 8) == pytest.approx(
        model.radial_null_displacement(1, 2) + model.radial_null_displacement(2, 8))


@pytest.mark.parametrize('w', [-1, float('nan'), 2])
def test_invalid_fluid(w):
    with pytest.raises(ValueError):
        FlatFLRW(w)


@pytest.mark.parametrize('t', [0, -1, True, float('inf')])
def test_invalid_time(t):
    with pytest.raises(ValueError):
        FlatFLRW().scale(t)


@pytest.mark.parametrize('cells', [8, 16, 32, 64])
def test_no_slip_channel_manufactured_solution(cells):
    data = channel_velocity(height=2, viscosity=.3, forcing=.2, cells=cells)
    assert data['velocity'][0] == data['velocity'][-1] == 0
    expected = [.2*y*(2-y)/(.6) for y in data['y']]
    assert data['velocity'] == pytest.approx(expected, abs=1e-12)


def test_channel_integrated_flux_converges_second_order():
    errors = []
    for cells in [8, 16, 32]:
        result = channel_velocity(height=1, viscosity=1, forcing=1, cells=cells)
        flux = sum(result['velocity']) / cells
        errors.append(abs(flux - 1/12))
    assert errors[0]/errors[1] == pytest.approx(4)
    assert errors[1]/errors[2] == pytest.approx(4)


def test_parent_lookup_and_cycles():
    assert canonical_children_cpu([0, 0, 1, 2], [3, 1, 0]) == [0, 0, 0]
    for parents, children in [([1, 0], [0]), ([0], [1]), ([False], [0])]:
        with pytest.raises(ValueError):
            canonical_children_cpu(parents, children)


def test_profile_receipt_does_not_invent_energy():
    receipt = profile_operation(lambda: sum(range(10)), backend='cpu-reference', repetitions=2)
    assert len(receipt.seconds) == 2
    assert min(receipt.seconds) >= 0
    assert receipt.energy_joules is None
    assert receipt.peak_vram_bytes is None
    assert isinstance(hardware_profile()['cuda_devices'], list)
    with pytest.raises(ValueError):
        profile_operation(lambda: None, backend='', repetitions=0)


def test_numpy_interchange_shape_dtype_and_loss_rejection():
    np = pytest.importorskip('numpy')
    from nablamath.adapters.numpy import to_data, from_data
    original = np.array([[1, 2], [3, 4]], dtype=np.int32)
    payload = to_data(original)
    assert np.array_equal(original, from_data(payload))
    assert from_data(payload).dtype == original.dtype
    for bad in [dict(payload, shape=[4]), dict(payload, dtype='object'),
                dict(payload, dtype='int8', values=[[1000, 2], [3, 4]])]:
        with pytest.raises(ValueError):
            from_data(bad)
    for invalid in [[complex(1, 2)], [float('nan')], ['text']]:
        with pytest.raises(ValueError):
            to_data(invalid)


def test_scipy_interoperability_exponential_ode():
    pytest.importorskip('scipy')
    from nablamath.adapters.scipy import solve_ivp
    result = solve_ivp(lambda t, y: [-y[0]], (0, 1), [1])
    assert result.y[0][-1] == pytest.approx(math.exp(-1), rel=1e-7)
    assert result.backend == 'scipy.solve_ivp'
    assert result.rtol == 1e-8


def test_public_f4_backend_selection_preserves_cpu():
    from nablamath.gpu.cuda_f4_reduction import modular_rref
    default = modular_rref([[1, 2], [3, 4]], 5)
    explicit = modular_rref([[1, 2], [3, 4]], 5, backend='cpu')
    assert default == explicit
    assert explicit.accelerated is False
    with pytest.raises(ValueError, match='Backend must'):
        modular_rref([[1]], 5, backend='fake-accelerator')


def test_public_cuda_selection_propagates_unavailability(monkeypatch):
    from nablamath.gpu.cuda_f4_reduction import modular_rref
    from nablamath.gpu.kernels import f4_cuda
    calls = []
    def unavailable():
        calls.append('requested')
        raise f4_cuda.CudaUnavailable('controlled unavailable dependency')
    monkeypatch.setattr(f4_cuda, 'CudaF4Backend', unavailable)
    with pytest.raises(f4_cuda.CudaUnavailable, match='controlled unavailable'):
        modular_rref([[1]], 5, backend='cuda')
    assert calls == ['requested']


def test_f4_rejects_backend_input_substitution_and_nonintegers():
    from nablamath.gpu.cuda_f4_reduction import modular_rref
    class Substitution:
        name = 'untrusted'
        accelerated = False
        def modular_rref(self, matrix, prime):
            matrix[0][0] = 0
            return matrix, []
    with pytest.raises(ArithmeticError):
        modular_rref([[1]], 5, backend=Substitution())
    for value in [1.5, True, '2']:
        with pytest.raises(ValueError):
            modular_rref([[value]], 5)


def test_forest_depth_budget_and_wide_forest():
    from nablamath.gpu.kernels.egraph_triton import canonical_children_cpu
    parents = [0] + list(range(1024))
    assert canonical_children_cpu(parents, [1024]) == [0]
    with pytest.raises(ValueError, match='depth'):
        canonical_children_cpu(parents + [1024], [1025])
    assert canonical_children_cpu([0] * 10000, range(10000)) == [0] * 10000
    with pytest.raises(ValueError, match='Cyclic'):
        canonical_children_cpu([0, 2, 3, 1], [0])


def test_forest_generator_budget_consumes_only_limit_plus_one(monkeypatch):
    from nablamath.gpu.kernels import egraph_triton as module
    monkeypatch.setattr(module, 'MAX_PARENTS', 3)
    consumed = []
    def infinite():
        while True:
            consumed.append(0)
            yield 0
    with pytest.raises(ValueError, match='Parent budget'):
        module.canonical_children_cpu(infinite(), [])
    assert len(consumed) == 4
    monkeypatch.setattr(module, 'MAX_CHILDREN', 2)
    with pytest.raises(ValueError, match='Child budget'):
        module.canonical_children_cpu([0], infinite())
    assert len(consumed) == 7


def test_forest_snapshot_survives_mutating_child_generator():
    from nablamath.gpu.kernels.egraph_triton import canonical_children_cpu
    parents = [0, 0, 1]
    def children():
        parents[:] = [2, 2, 2]
        yield 2
        yield 1
    assert canonical_children_cpu(parents, children()) == [0, 0]


def test_device_work_budget_precedes_optional_import(monkeypatch):
    from nablamath.gpu.kernels import egraph_triton as module
    monkeypatch.setattr(module, 'MAX_DEVICE_LOOKUPS', 2)
    with pytest.raises(ValueError, match='work budget'):
        module.canonical_children_triton([0, 0, 1], [2, 2])
