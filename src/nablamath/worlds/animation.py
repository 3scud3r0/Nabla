"""Self-contained SVG animation generated from actual simulation snapshots."""
from html import escape
import math
from pathlib import Path


def render_animation(result, *, max_frames=120, duration=6):
    if type(max_frames) is not int or not 2 <= max_frames <= 500 or not 0 < duration <= 60:
        raise ValueError('Orçamento de animação inválido')
    trajectory = result['trajectory']
    stride = max(1, math.ceil(len(trajectory)/max_frames))
    selected = list(trajectory[::stride])
    if selected[-1] != trajectory[-1]:
        selected.append(trajectory[-1])
    amplitude = max(max(abs(v) for v in state) for _,state in selected) or 1
    curves = []
    for _, state in selected:
        # PDE frames are spatial profiles; ODE frames display the state vector.
        curves.append(' '.join(f'{30+540*i/max(1,len(state)-1):.3f},{150-100*v/amplitude:.3f}' for i,v in enumerate(state)))
    values = ';'.join(curves)
    label = escape(result['model']+' | simulated states; not experimental evidence')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="340" viewBox="0 0 600 340">'
            f'<title>{label}</title><rect width="600" height="340" fill="white"/>'
            f'<text x="20" y="320">{label}</text><polyline fill="none" stroke="#1859a9" stroke-width="2" points="{curves[0]}">'
            f'<animate attributeName="points" dur="{duration}s" values="{values}" repeatCount="indefinite"/>'
            '</polyline></svg>\n')


def export_animation(result, destination, **options):
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        handle.write(render_animation(result, **options))
    return path
