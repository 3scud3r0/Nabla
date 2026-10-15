"""Version 1: bounded Pollard rho and deterministic primality below 2**64."""
from math import gcd, prod
CONTRACT_VERSION = 1


def is_prime64(n: int) -> bool:
    """Deterministic Miller-Rabin for the explicit unsigned 64-bit domain."""
    if type(n) is not int or not 0 <= n < 2**64:
        raise ValueError("requires unsigned 64-bit integer")
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if a % n == 0:
            continue
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def factorize64(n: int, *, max_iterations: int = 200000) -> tuple[int, ...]:
    """Sorted prime factors, with a global rho iteration budget.

    May fail on difficult semiprimes rather than return unverified factors.
    The empty tuple is the factorization of 1.
    """
    if type(n) is not int or not 1 <= n < 2**64:
        raise ValueError("requires positive unsigned 64-bit integer")
    if type(max_iterations) is not int or not 1 <= max_iterations <= 10000000:
        raise ValueError("invalid iteration budget")
    pending, factors, spent = [n], [], 0
    while pending:
        value = pending.pop()
        if value == 1:
            continue
        if is_prime64(value):
            factors.append(value)
            continue
        if value % 2 == 0:
            pending.extend((2, value // 2))
            continue
        divisor, c = value, 0
        while divisor == value:
            c += 1
            x = y = 2
            divisor = 1
            while divisor == 1:
                if spent >= max_iterations:
                    raise ArithmeticError("factorization iteration budget exhausted")
                spent += 1
                x = (x * x + c) % value
                y = (y * y + c) % value
                y = (y * y + c) % value
                divisor = gcd(abs(x - y), value)
        pending.extend((divisor, value // divisor))
    return tuple(sorted(factors))


def verify_factorization(n: int, factors: tuple[int, ...]) -> bool:
    """Check product and primality without trusting the factorizer."""
    if type(n) is not int or not 1 <= n < 2**64:
        return False
    return (all(type(p) is int and 2 <= p < 2**64 and is_prime64(p) for p in factors)
            and prod(factors) == n)
