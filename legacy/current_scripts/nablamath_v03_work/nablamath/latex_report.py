from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import json
import shutil
import subprocess
import textwrap
import time

from .core import Expr, Symbol
from .reports import StepByStepDeriver


@dataclass
class LatexReportResult:
    tex_path: Path
    pdf_path: Optional[Path]
    log_path: Optional[Path]
    success: bool
    message: str


class ExtremeLatexPDFReport:
    """Generate true LaTeX reports and optionally compile them with pdflatex.

    This module complements `ExtremePDFReport`. ReportLab is great for direct
    PDF generation; this class is for mathematically dense documents where
    formulas should be handled by a real TeX engine.
    """

    def __init__(self, title: str, output_dir: str | Path, filename: str = "nablamath_report"):
        self.title = title
        self.output_dir = Path(output_dir)
        self.filename = filename
        self.sections: List[str] = []
        self.metadata: Dict[str, Any] = {
            "generator": "NablaMath ExtremeLatexPDFReport",
            "created_at_unix": time.time(),
        }

    def add_raw_section(self, title: str, body_latex: str) -> "ExtremeLatexPDFReport":
        self.sections.append(f"\\section{{{_tex_escape(title)}}}\n{body_latex}\n")
        return self

    def add_expression_analysis(self, expr: Expr, variables: Sequence[Symbol]) -> "ExtremeLatexPDFReport":
        deriver = StepByStepDeriver()
        self.metadata.update({"expression": str(expr), "latex": expr.to_latex(), "variables": [v.name for v in variables]})
        body: List[str] = []
        body.append("\\subsection{Expressao original}\n")
        body.append(_display(fr"f={expr.to_latex()}"))
        body.append("A expressao e mantida como arvore simbolica, permitindo derivadas exatas, gradiente, Hessiana e avaliacao numerica.\n")

        grad = expr.grad(variables)
        grad_vec = r"\begin{bmatrix}" + r"\\".join(g.to_latex() for g in grad) + r"\end{bmatrix}"
        body.append("\\subsection{Gradiente}\n")
        body.append(_display(fr"\nabla f={grad_vec}"))
        for v in variables:
            body.append(f"\\subsubsection{{Derivada parcial em relacao a ${v.to_latex()}$}}\n")
            for step in deriver.derivative_steps(expr, v):
                body.append(f"\\paragraph{{{_tex_escape(step.title)}}} {_tex_escape(step.explanation)}\n")
                if step.latex:
                    body.append(_display(step.latex))

        H = expr.hessian(variables)
        hess = r"\begin{bmatrix}" + r"\\".join(" & ".join(c.to_latex() for c in row) for row in H) + r"\end{bmatrix}"
        body.append("\\subsection{Hessiana}\n")
        body.append(_display(fr"H_f={hess}"))
        body.append("A Hessiana resume a curvatura local da funcao. Em otimizacao, ela ajuda a distinguir minimos, maximos e pontos de sela.\n")
        self.add_raw_section("Analise simbolica minuciosa", "\n".join(body))
        return self

    def add_numerical_grid_section(self, expr: Expr, variables: Sequence[Symbol], domain: Mapping[str, Tuple[float, float]], samples: int = 7) -> "ExtremeLatexPDFReport":
        if len(variables) != 2:
            return self
        x, y = variables
        xs = _linspace(domain[x.name][0], domain[x.name][1], samples)
        ys = _linspace(domain[y.name][0], domain[y.name][1], samples)
        rows: List[str] = []
        best = None
        for xv in xs:
            for yv in ys:
                try:
                    val = expr.eval({x.name: xv, y.name: yv})
                    if best is None or val < best[2]:
                        best = (xv, yv, val)
                except Exception:
                    val = float("nan")
                rows.append(f"{xv:.3g} & {yv:.3g} & {val:.6g}\\\\")
        body = [
            "Esta varredura numerica simples avalia a funcao em uma malha pequena. Ela nao substitui otimizacao global, mas oferece diagnostico inicial do dominio.",
            "\\begin{center}\n\\begin{tabular}{rrr}\n\\toprule\n$x$ & $y$ & $f(x,y)$\\\\\n\\midrule",
            "\n".join(rows),
            "\\bottomrule\n\\end{tabular}\n\\end{center}",
        ]
        if best:
            body.append(_display(fr"\min_{{grid}} f \approx {best[2]:.6g}\quad \text{{em}}\quad (x,y)=({best[0]:.4g},{best[1]:.4g})"))
        self.add_raw_section("Calculo numerico em malha", "\n".join(body))
        return self

    def add_visualization_manifest(self, paths: Iterable[str | Path]) -> "ExtremeLatexPDFReport":
        items = []
        for p in paths:
            path = Path(p)
            items.append(f"\\item \texttt{{{_tex_escape(path.name)}}}: {_tex_escape(str(path))}")
        body = "O modulo de visualizacao empresarial exporta figuras interativas, metadados JSON e arquivos HTML reproduziveis.\\n\\begin{itemize}\n" + "\n".join(items) + "\n\\end{itemize}"
        self.add_raw_section("Manifesto de visualizacoes", body)
        return self

    def write_tex(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tex_path = self.output_dir / f"{self.filename}.tex"
        metadata_json = _tex_escape(json.dumps(self.metadata, indent=2, ensure_ascii=False))
        body = _document_preamble(self.title) + "\n".join(self.sections) + f"\n\\section{{Metadados reprodutiveis}}\n\\begin{{verbatim}}\n{json.dumps(self.metadata, indent=2, ensure_ascii=False)}\n\\end{{verbatim}}\n\\end{{document}}\n"
        tex_path.write_text(body, encoding="utf-8")
        return tex_path

    def compile_pdf(self, runs: int = 2) -> LatexReportResult:
        tex_path = self.write_tex()
        pdflatex = shutil.which("pdflatex")
        if not pdflatex:
            return LatexReportResult(tex_path, None, None, False, "pdflatex not found; TeX source generated only.")
        cmd = [pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
        log_path = self.output_dir / f"{self.filename}.compile.stdout.txt"
        stdout_all = []
        ok = True
        for _ in range(runs):
            proc = subprocess.run(cmd, cwd=str(self.output_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            stdout_all.append(proc.stdout)
            if proc.returncode != 0:
                ok = False
                break
        log_path.write_text("\n\n--- RUN ---\n\n".join(stdout_all), encoding="utf-8")
        pdf_path = self.output_dir / f"{self.filename}.pdf"
        return LatexReportResult(tex_path, pdf_path if pdf_path.exists() else None, log_path, ok and pdf_path.exists(), "compiled" if ok else "pdflatex failed")


def build_extreme_latex_function_report(expr: Expr, variables: Sequence[Symbol], output_dir: str | Path,
                                        filename: str = "nablamath_v03_extreme_latex_report",
                                        domain: Optional[Mapping[str, Tuple[float, float]]] = None,
                                        visual_paths: Optional[Iterable[str | Path]] = None) -> LatexReportResult:
    report = ExtremeLatexPDFReport("NablaMath v0.3: Relatorio matematico extremo", output_dir, filename)
    report.add_expression_analysis(expr, variables)
    if domain is not None:
        report.add_numerical_grid_section(expr, variables, domain)
    if visual_paths:
        report.add_visualization_manifest(visual_paths)
    return report.compile_pdf()


def _display(latex: str) -> str:
    return "\\[\n" + latex + "\n\\]\n"


def _linspace(a: float, b: float, n: int) -> List[float]:
    if n <= 1:
        return [float(a)]
    return [float(a + (b - a) * i / (n - 1)) for i in range(n)]


def _tex_escape(text: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in text)


def _document_preamble(title: str) -> str:
    return textwrap.dedent(fr'''
    \documentclass[11pt,a4paper]{{article}}
    \usepackage[utf8]{{inputenc}}
    \usepackage[T1]{{fontenc}}
    \usepackage{{lmodern}}
    \usepackage{{amsmath,amssymb,mathtools}}
    \usepackage{{geometry}}
    \usepackage{{booktabs}}
    \usepackage{{hyperref}}
    \usepackage{{xcolor}}
    \usepackage{{fancyhdr}}
    \geometry{{margin=1.7cm}}
    \pagestyle{{fancy}}
    \fancyhf{{}}
    \lhead{{NablaMath v0.3}}
    \rhead{{Relatorio extremo}}
    \cfoot{{\thepage}}
    \title{{{_tex_escape(title)}}}
    \author{{NablaMath}}
    \date{{\today}}
    \begin{{document}}
    \maketitle
    \begin{{abstract}}
    Este documento foi gerado por um modulo de relatorios matematicos em LaTeX. Ele combina expressao simbolica, derivadas passo a passo, gradiente, Hessiana, diagnostico numerico e manifesto de visualizacao.
    \end{{abstract}}
    \tableofcontents
    \newpage
    ''')
