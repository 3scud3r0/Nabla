"""Canonical signed-int64 rational protocol. No float or expression evaluation."""
import math
import re


def parse_fraction(source):
    if type(source) is not str or len(source)>42 or not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?',source):
        raise ValueError('Invalid canonical fraction')
    parts=source.split('/')
    n=int(parts[0]);d=int(parts[1]) if len(parts)==2 else 1
    if source.startswith('-0') or not -(1<<63)<=n<(1<<63) or not 1<=d<(1<<63):
        raise ValueError('Noncanonical or out-of-range fraction')
    if len(parts)==2 and (d==1 or n==0 or math.gcd(n,d)!=1):
        raise ValueError('Non-reduced fraction')
    return n,d
