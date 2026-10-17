"""Small state-vector and density-matrix simulator; qubit zero is most significant."""
import math
import random


def simulate_circuit(qubits, gates, *, shots=0, seed=0, density_matrix=False):
    if type(qubits) is not int or not 1 <= qubits <= 12:
        raise ValueError('Require 1–12 qubits')
    if not isinstance(gates, list) or len(gates) > 1000 or type(shots) is not int or not 0 <= shots <= 100000:
        raise ValueError('Circuit or shot budget exceeded')
    if type(seed) is not int or type(density_matrix) is not bool or (density_matrix and qubits > 8):
        raise ValueError('Invalid seed or density-matrix budget (maximum 8 qubits)')
    state = [0j]*(1 << qubits); state[0] = 1+0j
    root = 1/math.sqrt(2)
    matrices = {'X':((0,1),(1,0)), 'Y':((0,-1j),(1j,0)), 'Z':((1,0),(0,-1)),
                'H':((root,root),(root,-root)), 'S':((1,0),(0,1j)),
                'T':((1,0),(0,complex(root,root)))}
    for gate in gates:
        if not isinstance(gate,dict) or gate.get('gate') not in {*matrices,'CX','RZ'}:
            raise ValueError('Unknown quantum gate')
        name, target = gate['gate'], gate.get('target')
        expected = {'gate','target'} | ({'control'} if name == 'CX' else {'angle'} if name == 'RZ' else set())
        if set(gate) != expected or type(target) is not int or not 0 <= target < qubits:
            raise ValueError('Invalid gate fields or target')
        mask = 1 << (qubits-1-target)
        if name == 'CX':
            control = gate['control']
            if type(control) is not int or not 0 <= control < qubits or control == target:
                raise ValueError('Invalid control qubit')
            cmask = 1 << (qubits-1-control)
            for i in range(len(state)):
                if i & cmask and not i & mask:
                    state[i], state[i|mask] = state[i|mask], state[i]
        else:
            if name == 'RZ':
                angle = gate['angle']
                if type(angle) not in (int,float) or not math.isfinite(angle):
                    raise ValueError('Finite angle in radians required')
                phase = complex(math.cos(angle/2),math.sin(angle/2))
                matrix = ((phase.conjugate(),0),(0,phase))
            else:
                matrix = matrices[name]
            for i in range(len(state)):
                if not i & mask:
                    a,b = state[i],state[i|mask]
                    state[i],state[i|mask] = matrix[0][0]*a+matrix[0][1]*b, matrix[1][0]*a+matrix[1][1]*b
    probabilities = [abs(z)**2 for z in state]
    norm = sum(probabilities)
    if not math.isfinite(norm) or abs(norm-1) > 1e-10:
        raise ArithmeticError('Circuit lost normalization')
    rng = random.Random(seed)
    counts = {}
    # Random.choices avoids a shot-by-state Python loop.
    for sample in rng.choices(range(len(state)), weights=probabilities, k=shots):
        key = format(sample, f'0{qubits}b'); counts[key] = counts.get(key,0)+1
    pair = lambda z: [z.real,z.imag]
    result = {'state': [pair(z) for z in state], 'probabilities': probabilities, 'counts': counts,
              'seed':seed, 'qubit_order':'most_significant_first', 'norm_error':abs(norm-1),
              'limitations':'Ideal noiseless unitary simulation; no physical quantum hardware.'}
    if density_matrix:
        result['density_matrix'] = [[pair(a*b.conjugate()) for b in state] for a in state]
    return result


def apply_channel(density, kraus):
    """Apply a trace-preserving Kraus channel to a validated density matrix."""
    try:
        import numpy as np
    except ImportError as exc:
        raise ImportError('Install nablamath[research] for quantum channels') from exc
    rho = np.asarray(density, dtype=complex)
    if rho.ndim != 2 or rho.shape[0] != rho.shape[1] or not 1 <= rho.shape[0] <= 256:
        raise ValueError('Density matrix must be square and bounded')
    n = len(rho)
    if not np.isfinite(rho).all() or not np.allclose(rho,rho.conj().T,atol=1e-10,rtol=0) or abs(np.trace(rho)-1) > 1e-10 or np.linalg.eigvalsh(rho).min() < -1e-10:
        raise ValueError('Density matrix must be Hermitian, positive and trace one')
    if not 1 <= len(kraus) <= 64:
        raise ValueError('Require 1–64 Kraus operators')
    operators = [np.asarray(k,dtype=complex) for k in kraus]
    if any(k.shape != rho.shape or not np.isfinite(k).all() for k in operators):
        raise ValueError('Invalid Kraus operator')
    if not np.allclose(sum(k.conj().T@k for k in operators),np.eye(n),atol=1e-10,rtol=0):
        raise ValueError('Channel must preserve trace')
    return sum(k@rho@k.conj().T for k in operators)
