"""Multimodal sample exports, retaining exact values rather than SVG pixels."""
import csv
from itertools import islice
from io import StringIO
from ..core.semantic_ir import canonical_json, fingerprint
from .scientific_renderer import ScientificPlot, render_scientific_svg


def export_scientific_plot(plot):
    if not isinstance(plot, ScientificPlot):
        raise ValueError('ScientificPlot required')
    stream=StringIO(newline='')
    writer=csv.writer(stream)
    writer.writerow(('curve','x','y','lower','upper','x_unit','y_unit','uncertainty','source'))
    for original in plot.curves:
        curve=original.converted(plot.x_unit,plot.y_unit)
        for index,(x,y) in enumerate(curve.points):
            writer.writerow((curve.name,str(x),str(y),str(curve.lower[index]) if curve.lower else '',
                str(curve.upper[index]) if curve.upper else '',plot.x_unit.symbol,plot.y_unit.symbol,
                curve.uncertainty_kind,curve.source_id))
    outputs=dict(svg=render_scientific_svg(plot)['svg'],csv=stream.getvalue(),json=canonical_json(plot.to_data()))
    payload=dict(plot_id=plot.plot_id,outputs=outputs,
                 scope='Exact supplied samples and declared intervals; no continuous-curve accuracy claim')
    return {**payload,'export_id':fingerprint(payload)}


def replay_scientific_export(exported,plot):
    try:
        return exported==export_scientific_plot(plot)
    except (ValueError,TypeError,KeyError):
        return False


def export_animation(frames, times):
    frames=tuple(islice(iter(frames),101));times=tuple(islice(iter(times),101))
    if not 1<=len(frames)<=100 or len(times)!=len(frames):
        raise ValueError('1..100 frames and equal number of timestamps required')
    from ..core.semantic_ir import rational
    times=tuple(rational(value) for value in times)
    if times[0]<0 or any(left>=right for left,right in zip(times,times[1:])):
        raise ValueError('Nonnegative strictly increasing exact timestamps required')
    if any(not isinstance(frame,ScientificPlot) for frame in frames):
        raise ValueError('ScientificPlot frames required')
    first=frames[0]
    if any(frame.x_unit!=first.x_unit or frame.y_unit!=first.y_unit for frame in frames):
        raise ValueError('Animation axis units must remain fixed')
    payload=dict(schema_version=1,times=list(map(str,times)),
        frames=[export_scientific_plot(frame) for frame in frames],
        timing_unit='s',interpolation='none',
        scope='Discrete supplied frames; playback speed and human visual review are external')
    return {**payload,'animation_id':fingerprint(payload)}
