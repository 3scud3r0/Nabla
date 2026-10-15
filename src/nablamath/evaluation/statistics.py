"""Descriptive binomial uncertainty; sampling independence is not inferred."""
import math


def wilson_interval(successes: int, count: int) -> tuple[float, float]:
    """Two-sided nominal 95% Wilson interval, assuming independent Bernoulli trials."""
    if (type(count) is not int or type(successes) is not int
            or not 1 <= count <= 10000 or not 0 <= successes <= count):
        raise ValueError("Expected bounded nonempty binomial counts")
    z = 1.959963984540054
    proportion = successes / count
    denominator = 1 + z*z/count
    center = (proportion + z*z/(2*count)) / denominator
    radius = z * math.sqrt(proportion*(1-proportion)/count + z*z/(4*count*count)) / denominator
    return max(0.0, center-radius), min(1.0, center+radius)
