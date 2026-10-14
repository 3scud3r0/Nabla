"""Mathematical scenes with exact source coordinates and deterministic renderers."""
from .scene_graph import Scene, task_scene
from .svg_renderer import render_svg

__all__ = ["Scene", "task_scene", "render_svg"]

from .scene_graph import GeometryScene,Point,Segment,Circle,Polyline,Arrow
from .coordinate_system import CoordinateSystem
from .geometry_constraints import GeometryConstraint
__all__ += ['GeometryScene','Point','Segment','Circle','Polyline','Arrow','CoordinateSystem','GeometryConstraint']
