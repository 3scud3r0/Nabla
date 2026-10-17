"""FFT/Bluestein, orthonormal Haar wavelets, convolution and sampled signals.

The reference path is dependency-free O(n log n). Samples are real numbers or
[real, imaginary] pairs in the JSON catalog; amplitudes use the unnormalised
forward DFT convention. These are numerical transforms, not error enclosures.
"""
import cmath
import math

MAX_SAMPLES = 65536


def _complex(value):
    if isinstance(value,(list,tuple)) and len(value) == 2:
        value = complex(*value)
    else:
        if isinstance(value,bool):
            raise ValueError('Boolean samples are not numbers')
        value = complex(value)
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError('Samples must be finite')
    return value


def _samples(values):
    if not isinstance(values,(list,tuple)) or not 1 <= len(values) <= MAX_SAMPLES:
        raise ValueError('Require 1–65536 samples')
    return [_complex(value) for value in values]


def _radix2(values):
    n = len(values)
    result = list(values)
    j = 0
    for i in range(1,n):
        bit = n >> 1
        while j & bit:
            j ^= bit; bit >>= 1
        j ^= bit
        if i < j:
            result[i],result[j] = result[j],result[i]
    width = 2
    while width <= n:
        root = cmath.exp(-2j*math.pi/width)
        for start in range(0,n,width):
            factor = 1+0j
            for offset in range(width//2):
                a = result[start+offset]
                b = factor*result[start+offset+width//2]
                result[start+offset],result[start+offset+width//2] = a+b,a-b
                factor *= root
        width *= 2
    return result


def _forward(values):
    n = len(values)
    if n & (n-1) == 0:
        return _radix2(values)
    # Bluestein reduces arbitrary-length DFTs to a power-of-two convolution.
    size = 1 << (2*n-1).bit_length()
    a,b = [0j]*size,[0j]*size
    for index,value in enumerate(values):
        phase = cmath.exp(1j*math.pi*((index*index) % (2*n))/n)
        a[index] = value*phase.conjugate()
        b[index] = phase
        if index:
            b[size-index] = phase
    fa,fb = _radix2(a),_radix2(b)
    product = [x*y for x,y in zip(fa,fb)]
    convolution = [z.conjugate()/size for z in _radix2([z.conjugate() for z in product])]
    return [convolution[k]*cmath.exp(-1j*math.pi*((k*k) % (2*n))/n) for k in range(n)]


def fft(values, *, inverse=False):
    values = _samples(values)
    if type(inverse) is not bool:
        raise ValueError('inverse must be boolean')
    if inverse:
        return [x.conjugate()/len(values) for x in _forward([z.conjugate() for z in values])]
    return _forward(values)


def haar(values, *, levels=None, inverse=False):
    values = _samples(values); n = len(values)
    if n & (n-1):
        raise ValueError('Haar requires a power-of-two sample count')
    maximum = n.bit_length()-1
    levels = maximum if levels is None else levels
    if type(levels) is not int or not 0 <= levels <= maximum or type(inverse) is not bool:
        raise ValueError('Invalid Haar levels or inverse flag')
    result = list(values); root = math.sqrt(2)
    if inverse:
        width = n >> levels
        for _ in range(levels):
            expanded = []
            for a,d in zip(result[:width],result[width:2*width]):
                expanded.extend(((a+d)/root,(a-d)/root))
            result[:2*width] = expanded; width *= 2
    else:
        width = n
        for _ in range(levels):
            pairs = list(zip(result[:width:2],result[1:width:2]))
            result[:width] = [(a+b)/root for a,b in pairs]+[(a-b)/root for a,b in pairs]
            width //= 2
    return result


def convolve(values, other):
    left,right = _samples(values),_samples(other)
    n = len(left)+len(right)-1
    if n > MAX_SAMPLES:
        raise ValueError('Convolution output exceeds budget')
    size = 1 << (n-1).bit_length()
    a = _radix2(left+[0j]*(size-len(left)))
    b = _radix2(right+[0j]*(size-len(right)))
    return fft([x*y for x,y in zip(a,b)],inverse=True)[:n]


def spectral(kind, values, *, other=None, levels=None, sample_rate=1,
             cutoff=None, window_size=256, hop=128):
    values = _samples(values)
    if type(sample_rate) not in (int,float) or not math.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError('sample_rate must be finite and positive (Hz)')
    pairs = lambda data: [[float(z.real),float(z.imag)] for z in data]
    base = {'arithmetic':'floating_point','sample_rate':sample_rate,
            'convention':'DFT exp(-2pi*i*k*n/N), inverse scaled by 1/N'}
    if kind in {'fft','ifft'}:
        result = fft(values,inverse=kind == 'ifft')
    elif kind in {'haar','inverse_haar'}:
        result = haar(values,levels=levels,inverse=kind == 'inverse_haar')
        base['wavelet'] = 'orthonormal_haar'
        base['convention'] = 'packed [approx_L, detail_L, ..., detail_1], orthonormal Haar'
        base['levels'] = len(values).bit_length()-1 if levels is None else levels
    elif kind == 'convolve':
        result = convolve(values,other)
    elif kind in {'spectrum','lowpass'}:
        transformed = fft(values); n = len(values)
        frequencies = [(k if k < (n+1)//2 else k-n)*sample_rate/n for k in range(n)]
        if kind == 'spectrum':
            return {**base,'frequencies':frequencies,'power':[abs(z)**2/n**2 for z in transformed]}
        if type(cutoff) not in (int,float) or not math.isfinite(cutoff) or not 0 <= cutoff <= sample_rate/2:
            raise ValueError('cutoff must be within [0, Nyquist] in Hz')
        result = fft([z if abs(f) <= cutoff else 0j for z,f in zip(transformed,frequencies)],inverse=True)
    elif kind == 'stft':
        if type(window_size) is not int or not 2 <= window_size <= len(values) or type(hop) is not int or not 1 <= hop <= window_size:
            raise ValueError('Invalid STFT window/hop')
        window = [.5-.5*math.cos(2*math.pi*i/(window_size-1)) for i in range(window_size)]
        if (1+(len(values)-window_size)//hop)*window_size > 1000000:
            raise ValueError('STFT output exceeds budget')
        frames = [pairs(fft([values[start+i]*window[i] for i in range(window_size)]))
                  for start in range(0,len(values)-window_size+1,hop)]
        return {**base,'frames':frames,'times':[start/sample_rate for start in range(0,len(values)-window_size+1,hop)],
                'window':'symmetric_hann','window_size':window_size,'hop':hop}
    else:
        raise ValueError('Unknown spectral operation')
    return {**base,'values':pairs(result),'count':len(result)}


def calculate(kind, values, **options):
    """Execute through the canonical session and return an auditable Calculation."""
    from ..calc.session import CalculationSession
    return CalculationSession().execute('spectral',kind=kind,values=values,**options)
