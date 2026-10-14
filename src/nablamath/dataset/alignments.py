"""Check that numerical, symbolic and visual modalities describe the same task."""
from pathlib import Path
import json

from ..core.semantic_ir import ScientificTask
from ..graphics import task_scene, render_svg
from ..graphics.raster_renderer import render_png
from .scientific import validate_record


def validate_alignment(record: dict, directory: Path) -> bool:
    try:
        if not validate_record(record):
            return False
        task = ScientificTask.from_data(record['task'])
        from ..core.semantic_ir import rational
        solution = tuple(rational(v) for v in record['solution'])
        scene = task_scene(task, solution)
        prefix = Path(directory) / 'figures' / task.content_id
        return (json.loads(prefix.with_suffix('.json').read_text(encoding='utf-8')) == scene.to_data()
                and prefix.with_suffix('.svg').read_text(encoding='utf-8') == render_svg(scene)
                and prefix.with_suffix('.png').read_bytes() == render_png(scene))
    except (KeyError, ValueError, TypeError, OSError, ArithmeticError):
        return False
