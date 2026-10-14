"""Vector presentation retaining exact coordinates as metadata."""
from html import escape
import json
from .scene_graph import Scene


def render_svg(scene: Scene, width: int = 640, height: int = 400) -> str:
    from .scene_graph import GeometryScene
    if isinstance(scene, GeometryScene):
        from .rendering import render_rich_svg
        return render_rich_svg(scene, width, height)
    points = scene.pixels(width, height)
    geometry = " ".join(f"{x},{y}" for x, y in points)
    metadata = escape(json.dumps(scene.to_data(), sort_keys=True))
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
             f'<title>{escape(scene.label)}</title>', f'<metadata>{metadata}</metadata>',
             '<rect width="100%" height="100%" fill="white"/>']
    if scene.connected:
        lines.append(f'<polyline points="{geometry}" fill="none" stroke="#2456a6" stroke-width="2"/>')
    else:
        lines.extend(f'<circle cx="{x}" cy="{y}" r="4" fill="#2456a6"/>' for x, y in points)
    # Explicit extrema make the independent affine axis scaling visible.
    xs, ys = zip(*scene.points)
    lines.append(f'<text x="20" y="15" font-size="11">{escape(f"x=[{min(xs)}, {max(xs)}]; y=[{min(ys)}, {max(ys)}]")}</text>')
    return "\n".join(lines + ['</svg>', ''])
