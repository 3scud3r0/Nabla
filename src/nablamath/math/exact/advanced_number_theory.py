"""Certified finite integer arithmetic and computable number theory.

Every public function has a finite computational domain. Miller–Rabin uses the
proven deterministic witness set ONLY for unsigned 64-bit integers; factoring
uses bounded trial division rather than an undocumented probabilistic shortcut.
"""
from __future__ import annotations

from fractions import Fraction
from math import gcd, isqrt

from .laboratory import rational


UINT64 = 1 << 64
MAX_FACTOR = 10**12
MAX_DISCRETE_MODULUS = 10**9


def extended_gcd(a: int, b: int) -> tuple[int, int, int]:
    """Return nonnegative gcd and integral Bézout coefficients."""
    if type(a) is not int or type(b) is not int:
        raise TypeError("Euclidean algorithm requires integers")
    old_r, r = a, b
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    if old_r < 0:
        old_r, old_s, old_t = -old_r, -old_s, -old_t
    return old_r, old_s, old_t


def mod_inverse(a: int, modulus: int) -> int:
    """Inverse in Z/nZ; reject nonunits."""
    if type(modulus) is not int or modulus <= 1:
        raise ValueError("Modulus must exceed one")
    g, s, _ = extended_gcd(a, modulus)
    if g != 1:
        raise ValueError("Residue is not a unit")
    return s % modulus


def is_prime_64(n: int) -> bool:
    """Deterministic strong probable-prime decision for 0 <= n < 2**64."""
    if type(n) is not int or not 0 <= n < UINT64:
        raise ValueError("Primality contract is limited to unsigned 64-bit integers")
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    if n in small:
        return True
    if any(n % p == 0 for p in small):
        return False
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    # Valid deterministic witnesses for every n < 2**64.
    for a in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        a %= n
        if not a:
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


def prime_factorization(n: int) -> tuple[tuple[int, int], ...]:
    """Complete positive factorization for n <= 10**12 using trial division."""
    if type(n) is not int or not 1 <= n <= MAX_FACTOR:
        raise ValueError("Factorization supports integers in [1, 10**12]")
    factors = []
    exponent = 0
    while n % 2 == 0:
        n //= 2
        exponent += 1
    if exponent:
        factors.append((2, exponent))
    divisor = 3
    while divisor * divisor <= n:
        if n % divisor:
            divisor += 2
            continue
        exponent = 0
        while n % divisor == 0:
            exponent += 1
            n //= divisor
        factors.append((divisor, exponent))
        divisor += 2
    if n > 1:
        factors.append((n, 1))
    return tuple(factors)


def divisors(n: int) -> tuple[int, ...]:
    """Sorted divisors of a positive bounded integer."""
    out = [1]
    for p, multiplicity in prime_factorization(n):
        old = list(out)
        power = 1
        for _ in range(multiplicity):
            power *= p
            out.extend(x * power for x in old)
    return tuple(sorted(out))


def euler_phi(n: int) -> int:
    """Euler totient from the prime-power formula."""
    value = n
    for p, _ in prime_factorization(n):
        value = value // p * (p - 1)
    return value


def mobius(n: int) -> int:
    """Möbius μ(n) with μ(1)=1."""
    factors = prime_factorization(n)
    return 0 if any(k > 1 for _, k in factors) else (-1 if len(factors) % 2 else 1)


def divisor_sigma(n: int, power: int = 1) -> int:
    """Sum of d**power over positive divisors, 0 <= power <= 8."""
    if type(power) is not int or not 0 <= power <= 8:
        raise ValueError("Sigma exponent outside [0, 8]")
    result = 1
    for p, multiplicity in prime_factorization(n):
        result *= sum(p ** (power * i) for i in range(multiplicity + 1))
    return result


def multiplicative_order(a: int, modulus: int) -> int:
    """Least positive k with a**k == 1 (mod modulus), for units."""
    if type(modulus) is not int or not 2 <= modulus <= MAX_FACTOR:
        raise ValueError("Modulus outside factorization range")
    if type(a) is not int or gcd(a, modulus) != 1:
        raise ValueError("Residue must be a unit")
    order = euler_phi(modulus)
    for p, multiplicity in prime_factorization(order):
        for _ in range(multiplicity):
            if order % p == 0 and pow(a, order // p, modulus) == 1:
                order //= p
            else:
                break
    return order


def legendre_symbol(a: int, p: int) -> int:
    """Quadratic character in the odd prime field F_p."""
    if type(a) is not int or type(p) is not int or p < 3 or p % 2 == 0 or not is_prime_64(p):
        raise ValueError("Legendre symbol requires an odd 64-bit prime")
    value = pow(a % p, (p - 1) // 2, p)
    return -1 if value == p - 1 else value


def modular_square_roots(a: int, p: int) -> tuple[int, ...]:
    """Tonelli–Shanks roots of x^2=a mod an odd prime; return ALL 0, 1 or 2 roots."""
    if type(a) is not int or type(p) is not int or not 3 <= p < UINT64 or p % 2 == 0:
        raise ValueError("Expected an odd unsigned-64-bit prime")
    if not is_prime_64(p):
        raise ValueError("Modulus is not prime")
    a %= p
    if a == 0:
        return (0,)
    if legendre_symbol(a, p) == -1:
        return ()
    if p % 4 == 3:
        x = pow(a, (p + 1) // 4, p)
        return tuple(sorted({x, (-x) % p}))
    q, s = p - 1, 0
    while q % 2 == 0:
        q //= 2
        s += 1
    z = 2
    while legendre_symbol(z, p) != -1:
        z += 1
    m = s
    c = pow(z, q, p)
    t = pow(a, q, p)
    x = pow(a, (q + 1) // 2, p)
    while t != 1:
        i, t2 = 1, t * t % p
        while i < m and t2 != 1:
            i += 1
            t2 = t2 * t2 % p
        if i >= m:
            raise ArithmeticError("Tonelli–Shanks invariant failure")
        b = pow(c, 1 << (m - i - 1), p)
        x = x * b % p
        t = t * b * b % p
        c = b * b % p
        m = i
    roots = tuple(sorted({x, (-x) % p}))
    if any(root * root % p != a for root in roots):
        raise ArithmeticError("Modular root recheck failed")
    return roots


def primitive_root_prime(p: int) -> int:
    """Least primitive root modulo a prime <= 10**9."""
    if type(p) is not int or not 2 <= p <= MAX_DISCRETE_MODULUS or not is_prime_64(p):
        raise ValueError("Expected a prime <= 10**9")
    if p == 2:
        return 1
    factors = [q for q, _ in prime_factorization(p - 1)]
    for g in range(2, p):
        if all(pow(g, (p - 1) // q, p) != 1 for q in factors):
            return g
    raise ArithmeticError("Primitive root search invariant violated")


def discrete_log_bsgs(base: int, target: int, p: int) -> int | None:
    """Least discrete log in F_p*, where p is prime <= 10**9.

    A result is a verified exponent. None means target lies outside the subgroup
    generated by base; no unbounded or heuristic search is performed.
    """
    if type(p) is not int or not 2 <= p <= MAX_DISCRETE_MODULUS or not is_prime_64(p):
        raise ValueError("Discrete log requires prime modulus <= 10**9")
    if type(base) is not int or type(target) is not int:
        raise TypeError("Residues must be integers")
    base, target = base % p, target % p
    if base == 0 or target == 0:
        raise ValueError("Discrete logarithm requires nonzero field elements")
    order = multiplicative_order(base, p)
    size = isqrt(order) + 1
    baby = {}
    value = 1
    for j in range(size):
        baby.setdefault(value, j)
        value = value * base % p
    step = pow(mod_inverse(base, p), size, p)
    giant = target
    solutions = []
    for i in range(size + 1):
        if giant in baby:
            exponent = (i * size + baby[giant]) % order
            if pow(base, exponent, p) == target:
                solutions.append(exponent)
        giant = giant * step % p
    return min(solutions) if solutions else None


def continued_fraction_sqrt(d: int) -> tuple[int, tuple[int, ...]]:
    """Periodic simple continued fraction for nonsquare sqrt(d), d <= 10**6."""
    if type(d) is not int or not 2 <= d <= 10**6:
        raise ValueError("Square-root radicand outside [2, 10**6]")
    a0 = isqrt(d)
    if a0 * a0 == d:
        raise ValueError("Periodic expansion requires a nonsquare")
    m, denominator, a = 0, 1, a0
    period = []
    for _ in range(10000):
        m = denominator * a - m
        denominator = (d - m * m) // denominator
        if denominator <= 0:
            raise ArithmeticError("Continued-fraction denominator invariant")
        a = (a0 + m) // denominator
        period.append(a)
        if a == 2 * a0:
            return a0, tuple(period)
    raise ArithmeticError("Continued-fraction period budget exceeded")


def pell_min_solution(d: int) -> tuple[int, int]:
    """Smallest positive solution x^2 - d*y^2 = 1, d nonsquare <= 10**6."""
    a0, period = continued_fraction_sqrt(d)
    p2, p1 = 0, 1
    q2, q1 = 1, 0
    for i in range(2 * len(period) + 1):
        a = a0 if i == 0 else period[(i - 1) % len(period)]
        p = a * p1 + p2
        q = a * q1 + q2
        if p * p - d * q * q == 1:
            return p, q
        p2, p1 = p1, p
        q2, q1 = q1, q
    raise ArithmeticError("Pell convergence invariant violated")


def farey_neighbors(x: Fraction | int | str, bound: int) -> tuple[Fraction, Fraction]:
    """Nearest Farey fractions immediately around x in [0,1], order <= bound.

    If x is itself in the Farey sequence, the lower and upper neighbors are
    still strict; endpoints 0 and 1 are excluded by contract.
    """
    x = rational(x)
    if not 0 < x < 1 or type(bound) is not int or not 1 <= bound <= 20000:
        raise ValueError("Requires interior rational x and Farey order <= 20000")
    left, right = Fraction(0), Fraction(1)
    for denominator in range(1, bound + 1):
        numerator = (x.numerator * denominator) // x.denominator
        candidates = (numerator, numerator + 1)
        for a in candidates:
            if not 0 <= a <= denominator:
                continue
            candidate = Fraction(a, denominator)
            if left < candidate < x:
                left = candidate
            if x < candidate < right:
                right = candidate
    return left, right


__all__ = [
    "extended_gcd", "mod_inverse", "is_prime_64", "prime_factorization",
    "divisors", "euler_phi", "mobius", "divisor_sigma", "multiplicative_order",
    "legendre_symbol", "modular_square_roots", "primitive_root_prime",
    "discrete_log_bsgs", "continued_fraction_sqrt", "pell_min_solution",
    "farey_neighbors",
]
