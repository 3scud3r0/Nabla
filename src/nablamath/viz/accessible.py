"""Accessible scientific sample tables paired with replayable SVG exports."""
from html import escape
from ..graphics.scientific_renderer import ScientificPlot, render_scientific_svg
from ..core.semantic_ir import fingerprint


def accessible_plot(plot):
    if not isinstance(plot, ScientificPlot):
        raise ValueError('ScientificPlot required')
    rendered = render_scientific_svg(plot)
    descriptions = []
    tables = []
    for original in plot.curves:
        curve = original.converted(plot.x_unit, plot.y_unit)
        descriptions.append(f'{curve.name}: {len(curve.points)} samples; uncertainty: {curve.uncertainty_kind}; source: {curve.source_id}')
        rows = []
        for index, (x, y) in enumerate(curve.points):
            interval = '' if not curve.lower else f'{curve.lower[index]} .. {curve.upper[index]}'
            rows.append('<tr>'+''.join('<td>'+escape(str(value))+'</td>' for value in (x,y,interval))+'</tr>')
        tables.append('<table><caption>'+escape(curve.name)+'</caption><thead><tr>'+''.join('<th scope="col">'+escape(value)+'</th>' for value in (f'{plot.x_label} [{plot.x_unit.symbol}]',f'{plot.y_label} [{plot.y_unit.symbol}]','Declared uncertainty'))+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table>')
    text = plot.title+'\n'+'\n'.join(descriptions)+'\n'+plot.limitations
    html = '<figure>'+rendered['svg']+'<figcaption>'+escape(text)+'</figcaption></figure>'+''.join(tables)
    payload = dict(plot_id=plot.plot_id, svg_render_id=rendered['receipt']['render_id'],
                   alternative_text=text, sample_count=sum(len(c.points) for c in plot.curves),
                   units=dict(x=plot.x_unit.symbol,y=plot.y_unit.symbol),
                   limitations='Tabular alternative and semantic replay do not establish human legibility')
    return dict(html=html, svg=rendered['svg'], accessibility=payload, content_id=fingerprint(payload))


def replay_accessible_plot(result, plot):
    try:
        return result == accessible_plot(plot)
    except (ValueError, TypeError, KeyError):
        return False
