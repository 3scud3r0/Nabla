"""Bounded Dormand–Prince 5(4) integration for finite, non-stiff ODE states.

The embedded estimate controls *local* error. It is not a rigorous enclosure of
accumulated error and does not certify the physical model or handle stiffness.
"""
import math

_A = ((), (1/5,), (3/40, 9/40), (44/45, -56/15, 32/9),
      (19372/6561, -25360/2187, 64448/6561, -212/729),
      (9017/3168, -355/33, 46732/5247, 49/176, -5103/18656),
      (35/384, 0, 500/1113, 125/192, -2187/6784, 11/84))
_C = (0, 1/5, 3/10, 4/5, 8/9, 1, 1)
_B = (35/384, 0, 500/1113, 125/192, -2187/6784, 11/84, 0)
_LOW = (5179/57600, 0, 7571/16695, 393/640, -92097/339200, 187/2100, 1/40)


def integrate_adaptive(function, initial, start, end, *, atol=1e-9, rtol=1e-6,
                       initial_step=None, max_attempts=100000, min_step=1e-14):
    """Return trajectory and step diagnostics or fail without a success artifact."""
    parameters = (start, end, atol, rtol, min_step)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in parameters):
        raise ValueError('Parâmetros finitos obrigatórios')
    if end <= start or atol <= 0 or rtol < 0 or min_step <= 0:
        raise ValueError('Intervalo ou tolerâncias inválidos')
    if type(max_attempts) is not int or not 1 <= max_attempts <= 100000:
        raise ValueError('Orçamento de passos inválido')
    raw = tuple(initial)
    if not 1 <= len(raw) <= 128 or any(isinstance(v, bool) or not math.isfinite(v) for v in raw):
        raise ValueError('Estado finito de dimensão 1–128 obrigatório')
    state = tuple(float(v) for v in raw)
    step = (end-start)/100 if initial_step is None else initial_step
    if isinstance(step, bool) or not math.isfinite(step) or step <= 0:
        raise ValueError('Passo inicial inválido')
    time = float(start)
    trajectory = [(time, state)]
    accepted, rejected, evaluations, worst = 0, 0, 0, 0.0
    for _ in range(max_attempts):
        h = min(step, end-time)
        if time+h == time or (h < min_step and end-time > min_step):
            raise ValueError('Passo mínimo atingido; possível rigidez ou tolerância inviável')
        stages = []
        for c, coefficients in zip(_C, _A):
            value = tuple(state[j]+h*sum(a*k[j] for a, k in zip(coefficients, stages))
                          for j in range(len(state)))
            if not all(math.isfinite(v) for v in value):
                raise ValueError('Estado intermediário não finito')
            derivative = tuple(function(time+c*h, value))
            evaluations += 1
            if len(derivative) != len(state) or any(isinstance(v, bool) or not math.isfinite(v) for v in derivative):
                raise ValueError('Derivada não finita ou dimensão incompatível')
            stages.append(derivative)
        high = tuple(state[j]+h*sum(b*k[j] for b, k in zip(_B, stages)) for j in range(len(state)))
        if not all(math.isfinite(v) for v in high):
            raise ValueError('Solução não finita')
        error = max(abs(h*sum((b-low)*k[j] for b, low, k in zip(_B, _LOW, stages))) /
                    (atol+rtol*max(abs(state[j]), abs(high[j]))) for j in range(len(state)))
        if not math.isfinite(error):
            raise ValueError('Estimativa de erro não finita')
        if error <= 1:
            time = float(end) if h == end-time else time+h
            state = high
            trajectory.append((time, state))
            accepted += 1
            worst = max(worst, error)
            if time == end:
                return {'method': 'dopri54', 'trajectory': trajectory, 'final': state,
                        'initial_step': initial_step, 'accepted_steps': accepted, 'rejected_steps': rejected,
                        'derivative_evaluations': evaluations, 'atol': atol, 'rtol': rtol,
                        'max_accepted_local_error_ratio': worst,
                        'global_error_certified': False,
                        'limitations': 'Embedded local error estimate; non-stiff finite ODEs only.'}
        else:
            rejected += 1
        step = h*min(5.0, max(0.1, 0.9*error**(-0.2) if error else 5.0))
    raise ValueError('Orçamento de passos adaptativos esgotado')
