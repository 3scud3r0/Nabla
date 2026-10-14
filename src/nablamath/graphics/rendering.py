"""Shared primitive backends: escaped SVG and deterministic annotated RGB PNG."""
from html import escape
from io import BytesIO
from ..core.semantic_ir import canonical_json
from .layout import build_primitives


def render_rich_svg(scene,width=800,height=600):
    primitives,layout=build_primitives(scene,width,height)
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
           f'<title>{escape(scene.title)}</title>',
           '<metadata>'+escape(canonical_json({'scene':scene.to_data(),'layout':layout}))+'</metadata>',
           '<rect width="100%" height="100%" fill="white"/>']
    for p in primitives:
        if p['kind']=='line':
            (x1,y1),(x2,y2)=p['points']
            lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{p["color"]}" stroke-width="{p["width"]}"/>')
        elif p['kind']=='point':
            x,y=p['point'];lines.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{p["color"]}"/>')
        else:
            x,y=p['position'];lines.append(f'<text x="{x}" y="{y+12}" fill="{p["color"]}" font-family="monospace" font-size="12">{escape(p["text"])}</text>')
    return '\n'.join(lines+['</svg>',''])


def render_rich_png(scene,width=800,height=600):
    try:
        from PIL import Image,ImageDraw,ImageFont,PngImagePlugin
    except ImportError as exc:
        raise RuntimeError('Raster geometrico requer o extra graphics (Pillow)') from exc
    primitives,layout=build_primitives(scene,width,height)
    image=Image.new('RGB',(width,height),'white');draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=12)
    for p in primitives:
        if p['kind']=='line':draw.line(p['points'],fill=p['color'],width=p['width'])
        elif p['kind']=='point':
            x,y=p['point'];draw.ellipse((x-3,y-3,x+3,y+3),fill=p['color'])
        else:draw.text(p['position'],p['text'],fill=p['color'],font=font)
    metadata=PngImagePlugin.PngInfo()
    metadata.add_itxt('NablaScene',canonical_json(scene.to_data()))
    metadata.add_itxt('NablaLayout',canonical_json(layout))
    output=BytesIO();image.save(output,format='PNG',pnginfo=metadata,optimize=False,compress_level=9)
    return output.getvalue()
