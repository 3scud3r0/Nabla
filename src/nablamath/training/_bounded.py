"""Consume caller iterables without materializing beyond a declared item budget."""
from itertools import islice


def bounded_tuple(values, maximum, *, label='items'):
    try:
        result=tuple(islice(iter(values),maximum+1))
    except TypeError as exc:
        raise ValueError(f'Iterable {label} required') from exc
    if len(result)>maximum:
        raise ValueError(f'Too many {label}')
    return result
