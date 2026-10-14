"""Dependency-free deterministic RGB PNG, using the same scene transform as SVG."""
import struct
import json
import zlib
from .scene_graph import Scene


def render_png(scene: Scene, width: int = 640, height: int = 400) -> bytes:
    from .scene_graph import GeometryScene
    if isinstance(scene, GeometryScene):
        from .rendering import render_rich_png
        return render_rich_png(scene, width, height)
    points = scene.pixels(width, height)
    pixels = bytearray(b'\xff' * (width * height * 3))

    def dot(x: int, y: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            offset = 3 * (y * width + x)
            pixels[offset:offset + 3] = bytes((36, 86, 166))

    def line(a: tuple[int, int], b: tuple[int, int]) -> None:
        x, y = a
        tx, ty = b
        dx, dy = abs(tx - x), -abs(ty - y)
        sx, sy = (1 if x < tx else -1), (1 if y < ty else -1)
        error = dx + dy
        while True:
            dot(x, y)
            if (x, y) == (tx, ty):
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x += sx
            if twice <= dx:
                error += dx
                y += sy

    if scene.connected:
        for a, b in zip(points, points[1:]):
            line(a, b)
    for x, y in points:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                dot(x + dx, y + dy)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    scanlines = b''.join(b'\0' + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height))
    metadata = ("Description\0" + json.dumps(scene.to_data(), sort_keys=True)).encode('ascii')
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'tEXt', metadata) + chunk(b'IDAT', zlib.compress(scanlines, 9)) + chunk(b'IEND', b''))
