from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from nablamath import *

out = ROOT / "outputs_v03_pdf"
out.mkdir(exist_ok=True)
x, y = symbols("x y")
f = parse_expr("(x^2 + y - 11)^2 + (x + y^2 - 7)^2", {"x": x, "y": y})
result = build_extreme_latex_function_report(
    f, [x, y], out,
    domain={"x": (-6, 6), "y": (-6, 6)},
    visual_paths=["outputs_v03/visual/surface3d.html", "outputs_v03/visual/gradient_field.html"],
)
print("success", result.success)
print("tex", result.tex_path)
print("pdf", result.pdf_path)
print("log", result.log_path)
print("message", result.message)
