"""Version 1: real Lambert W with explicit branches; floating approximations."""
import math
from decimal import Decimal, localcontext
CONTRACT_VERSION = 1


def lambert_w(x: float, branch: int = 0, *, tolerance: float = 1e-13,
              max_iterations: int = 2000) -> float:
    """Bounded bisection on real branch 0 or -1 (zero excluded on -1)."""
    if type(branch) is not int or branch not in (0, -1):
        raise ValueError("real branch must be 0 or -1")
    if not math.isfinite(x) or x < -1 / math.e or (branch == -1 and x >= 0):
        raise ValueError("argument outside the real branch domain")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be finite and positive")
    if type(max_iterations) is not int or not 1 <= max_iterations <= 10000:
        raise ValueError("invalid iteration budget")
    if x == -1 / math.e:
        return -1.0
    if x == 0:
        return 0.0
    if abs(x + 1 / math.e) < 1e-8:
        # Log and direct binary64 residuals lose the quadratic separation of
        # the two roots here. Decimal evaluates that residual without cancellation.
        with localcontext() as context:
            context.prec = 80
            target = Decimal.from_float(float(x))
            lo, hi = ((Decimal(-1), Decimal(0)) if branch == 0
                      else (Decimal(-2), Decimal(-1)))
            threshold = Decimal.from_float(tolerance)
            for _ in range(max_iterations):
                mid = (lo + hi) / 2
                if hi - lo <= threshold:
                    return float(mid)
                value = mid * mid.exp() - target
                if (value < 0) == (branch == 0):
                    lo = mid
                else:
                    hi = mid
        raise ArithmeticError("Lambert W iteration budget exhausted")
    if x > 0:
        target = math.log(x)
        lo, hi = 0.0, max(1.0, target + 1)
        residual = lambda w: w + math.log(w) - target
    else:
        target = math.log(-x)
        residual = lambda w: w + math.log(-w) - target
        lo, hi = (-1.0, 0.0) if branch == 0 else (min(-2.0, 2 * target), -1.0)
    increasing = branch == -1 or x > 0
    for _ in range(max_iterations):
        mid = (lo + hi) / 2
        if mid == lo or mid == hi or hi - lo <= tolerance * max(5e-324, abs(mid)):
            return mid
        value = residual(mid)
        if value == 0:
            return mid
        if (value < 0) == increasing:
            lo = mid
        else:
            hi = mid
    raise ArithmeticError("Lambert W iteration budget exhausted")
