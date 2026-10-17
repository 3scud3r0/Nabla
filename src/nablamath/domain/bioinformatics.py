"""Global DNA/RNA/protein alignment by Needleman-Wunsch, with deterministic ties."""
import math


def align_sequences(first, second, *, match=1, mismatch=-1, gap=-1):
    if any(not isinstance(s, str) or not s or not s.isascii() or not s.isalpha() for s in (first, second)):
        raise ValueError('Sequences must be nonempty ASCII letters; gaps are inserted by the aligner')
    if len(first)*len(second) > 1000000 or max(len(first), len(second)) > 10000:
        raise ValueError('Alignment exceeds budget')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in (match,mismatch,gap)):
        raise ValueError('Scores must be finite numbers')
    first, second = first.upper(), second.upper()
    n, m = len(first), len(second)
    scores = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1):
        scores[i][0] = i*gap
    for j in range(m+1):
        scores[0][j] = j*gap
    for i in range(1,n+1):
        for j in range(1,m+1):
            scores[i][j] = max(scores[i-1][j-1]+(match if first[i-1] == second[j-1] else mismatch),
                               scores[i-1][j]+gap, scores[i][j-1]+gap)
    a, b, i, j = [], [], n, m
    while i or j:
        if i and j and scores[i][j] == scores[i-1][j-1]+(match if first[i-1] == second[j-1] else mismatch):
            a.append(first[i-1]); b.append(second[j-1]); i -= 1; j -= 1
        elif i and scores[i][j] == scores[i-1][j]+gap:
            a.append(first[i-1]); b.append('-'); i -= 1
        else:
            a.append('-'); b.append(second[j-1]); j -= 1
    a, b = ''.join(reversed(a)), ''.join(reversed(b))
    return {'first': a, 'second': b, 'score': scores[n][m],
            'identity': sum(x == y for x,y in zip(a,b))/len(a),
            'algorithm': 'needleman_wunsch', 'scoring': {'match':match,'mismatch':mismatch,'gap':gap},
            'limitations': 'Global alignment with linear gaps; no evolutionary or clinical inference.'}


def gc_content(sequence):
    if not isinstance(sequence, str) or not sequence or set(sequence.upper()) - set('ACGT'):
        raise ValueError('An unambiguous DNA sequence is required')
    sequence = sequence.upper()
    return (sequence.count('G') + sequence.count('C'))/len(sequence)
