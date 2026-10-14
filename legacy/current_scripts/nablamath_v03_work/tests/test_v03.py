from pathlib import Path
from nablamath import *


def test_step_deriver_and_visual_spec(tmp_path):
    x, y = symbols("x y")
    f = (x**2 + y - 11)**2 + (x + y**2 - 7)**2
    steps = StepByStepDeriver().gradient_steps(f, [x, y])
    assert len(steps) >= 3
    fig = plot3d_extreme(f, [x, y], {"x": (-1, 1), "y": (-1, 1)}, resolution=8)
    meta = fig.export_metadata(tmp_path / "m.json")
    assert meta.exists()
    assert fig.metadata.diagnostics["finite_count"] > 0


def test_pdf_report_builds(tmp_path):
    x, y = symbols("x y")
    f = (x**2 + y - 11)**2 + (x + y**2 - 7)**2
    pdf = build_function_report(f, [x, y], tmp_path / "report.pdf", start={"x":0.0,"y":0.0}, bounds={"x":(-2,2),"y":(-2,2)})
    assert pdf.exists()
    assert pdf.stat().st_size > 5000
