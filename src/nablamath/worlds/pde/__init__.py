"""FTCS heat solver, zero Dirichlet boundaries and a closed-form sine oracle."""
import math
from ..model_spec import HeatModelSpec
from ..mesh import UniformMesh
from ..integrators import diffusion_ratio


def solve_heat(model: HeatModelSpec, *, cells=20, steps=200, snapshot_stride=1):
    mesh = UniformMesh(model.length, cells)
    if type(steps) is not int or not 2 <= steps <= 100000:
        raise ValueError('EDP requer 2–100000 passos')
    if type(snapshot_stride) is not int or not 1 <= snapshot_stride <= steps:
        raise ValueError('Intervalo de snapshots inválido')
    if (steps//snapshot_stride+2)*(cells+1) > 2000000 or steps*cells > 10000000:
        raise ValueError('Orçamento de simulação excedido')
    dt = model.duration/steps
    ratio = diffusion_ratio(model.diffusivity, dt, mesh.spacing)
    state = tuple(model.reference(0, x) for x in mesh.nodes)
    state = (0.0, *state[1:-1], 0.0)
    trajectory = [(0.0, state)]
    balance, energy_increase = 0.0, 0.0
    def mass(values):
        return mesh.spacing*sum(values[1:-1])
    def energy(values):
        return mesh.spacing*sum(v*v for v in values)
    for index in range(1, steps+1):
        new = (0.0, *(state[i]+ratio*(state[i-1]-2*state[i]+state[i+1]) for i in range(1, cells)), 0.0)
        expected_change = dt*model.diffusivity/mesh.spacing*(state[0]-state[1]+state[-1]-state[-2])
        balance = max(balance, abs((mass(new)-mass(state))-expected_change))
        energy_increase = max(energy_increase, energy(new)-energy(state))
        if not all(math.isfinite(v) for v in new):
            raise ArithmeticError('Estado térmico não finito')
        state = new
        if index % snapshot_stride == 0 or index == steps:
            trajectory.append((index*dt, state))
    reference = tuple(model.reference(model.duration, x) for x in mesh.nodes)
    return {'schema_version': 1, 'model': 'heat_1d', 'model_spec': model.to_data(), 'model_id': model.content_id,
            'method': 'ftcs', 'cells': cells, 'steps': steps, 'dx': mesh.spacing, 'dt': dt,
            'stability_ratio': ratio, 'positions': mesh.nodes, 'initial': trajectory[0][1],
            'final': state, 'reference': reference, 'trajectory': tuple(trajectory),
            'max_component_error': max(abs(a-b) for a,b in zip(state, reference)),
            'flux_balance_residual': balance, 'max_energy_increase': energy_increase,
            'units': {'time': 's', 'position': 'm', 'state': 'K', 'flux_balance': 'K*m'},
            'boundary': 'zero_dirichlet', 'evidence': 'comparison_with_analytic_reference',
            'limitations': 'Linear ideal diffusion, no measured observations or experimental validation.'}
