from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import json
import math
import tempfile
import time

import numpy as np

from .core import Add, Cos, Equation, Exp, Expr, Log, Mul, Neg, Number, Pow, Sin, Sqrt, Symbol, UnaryFunction
from .optimize import gradient_descent, adam_optimize, newton_optimize, random_search


@dataclass
class CalculationStep:
    title: str
    latex: Optional[str] = None
    explanation: str = ""
    result_latex: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportAsset:
    path: Path
    caption: str = ""
    kind: str = "image"


@dataclass
class ReportSection:
    title: str
    paragraphs: List[str] = field(default_factory=list)
    steps: List[CalculationStep] = field(default_factory=list)
    assets: List[ReportAsset] = field(default_factory=list)
    tables: List[Tuple[List[str], List[List[Any]]]] = field(default_factory=list)


class LatexEquationRenderer:
    """Render LaTeX/mathtext snippets to transparent PNG images for PDF reports."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.counter = 0

    def render(self, latex: str, fontsize: int = 18, dpi: int = 220) -> Optional[Path]:
        self.counter += 1
        out = self.output_dir / f"equation_{self.counter:04d}.png"
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig = plt.figure(figsize=(0.01, 0.01))
            text = fig.text(0, 0, f"${latex}$", fontsize=fontsize)
            fig.canvas.draw()
            bbox = text.get_window_extent()
            width = max(1.0, bbox.width / dpi)
            height = max(0.4, bbox.height / dpi)
            plt.close(fig)
            fig = plt.figure(figsize=(width + 0.12, height + 0.10))
            fig.text(0.02, 0.12, f"${latex}$", fontsize=fontsize)
            fig.savefig(out, dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0.05)
            plt.close(fig)
            return out
        except Exception:
            return None


class StepByStepDeriver:
    """Symbolic derivation trace generator.

    This is intentionally explicit and educational: it records which derivative
    rule is being used before returning the symbolic derivative supplied by
    NablaMath's expression engine.
    """

    def derivative_steps(self, expr: Expr, var: Symbol) -> List[CalculationStep]:
        steps: List[CalculationStep] = []
        self._walk_derivative(expr, var, steps, depth=0)
        result = expr.diff(var).simplify()
        steps.append(CalculationStep(
            title="Resultado final da derivada",
            latex=fr"\frac{{\partial}}{{\partial {var.to_latex()}}}\left({expr.to_latex()}\right)={result.to_latex()}",
            explanation="A expressao final e simplificada pelo motor simbolico da NablaMath.",
            result_latex=result.to_latex(),
        ))
        return steps

    def gradient_steps(self, expr: Expr, variables: Sequence[Symbol]) -> List[CalculationStep]:
        steps: List[CalculationStep] = []
        grad = expr.grad(variables)
        vector = r"\begin{bmatrix}" + r"\\".join(g.to_latex() for g in grad) + r"\end{bmatrix}"
        steps.append(CalculationStep(
            title="Definicao do gradiente",
            latex=fr"\nabla f = {vector}",
            explanation="O gradiente agrupa todas as derivadas parciais de primeira ordem.",
        ))
        for v in variables:
            steps.extend(self.derivative_steps(expr, v))
        return steps

    def hessian_steps(self, expr: Expr, variables: Sequence[Symbol]) -> List[CalculationStep]:
        H = expr.hessian(variables)
        matrix = r"\begin{bmatrix}" + r"\\".join(" & ".join(cell.to_latex() for cell in row) for row in H) + r"\end{bmatrix}"
        return [CalculationStep(
            title="Matriz Hessiana",
            latex=fr"H_f = {matrix}",
            explanation="A Hessiana contem todas as derivadas parciais de segunda ordem. Ela e usada para classificar curvatura local, minimo, maximo e ponto de sela.",
        )]

    def _walk_derivative(self, expr: Expr, var: Symbol, steps: List[CalculationStep], depth: int) -> None:
        if depth > 6:
            return
        if isinstance(expr, Number):
            steps.append(CalculationStep("Regra da constante", fr"\frac{{d}}{{d{var.to_latex()}}}{expr.to_latex()}=0", "Toda constante tem derivada zero."))
        elif isinstance(expr, Symbol):
            val = "1" if expr.name == var.name else "0"
            steps.append(CalculationStep("Regra do simbolo", fr"\frac{{d}}{{d{var.to_latex()}}}{expr.to_latex()}={val}", "A derivada de uma variavel em relacao a ela mesma e 1; em relacao a outra variavel e 0."))
        elif isinstance(expr, Add):
            steps.append(CalculationStep("Regra da soma", fr"\frac{{d}}{{d{var.to_latex()}}}\left({expr.to_latex()}\right)=\frac{{d}}{{d{var.to_latex()}}}\left({expr.left.to_latex()}\right)+\frac{{d}}{{d{var.to_latex()}}}\left({expr.right.to_latex()}\right)", "Derivamos cada parcela separadamente."))
            self._walk_derivative(expr.left, var, steps, depth + 1)
            self._walk_derivative(expr.right, var, steps, depth + 1)
        elif isinstance(expr, Mul):
            steps.append(CalculationStep("Regra do produto", fr"(uv)'=u'v+uv'", f"Aqui u={expr.left.to_latex()} e v={expr.right.to_latex()}."))
            self._walk_derivative(expr.left, var, steps, depth + 1)
            self._walk_derivative(expr.right, var, steps, depth + 1)
        elif isinstance(expr, Neg):
            steps.append(CalculationStep("Regra do sinal negativo", fr"(-u)'=-u'", f"Aqui u={expr.expr.to_latex()}."))
            self._walk_derivative(expr.expr, var, steps, depth + 1)
        elif isinstance(expr, Pow):
            if isinstance(expr.exponent, Number):
                steps.append(CalculationStep("Regra da potencia com cadeia", fr"\frac{{d}}{{d{var.to_latex()}}}u^n=n u^{{n-1}}u'", f"Aqui u={expr.base.to_latex()} e n={expr.exponent.to_latex()}."))
            else:
                steps.append(CalculationStep("Regra geral da potencia", fr"(u^v)'=u^v\left(v'\ln u+v\frac{{u'}}{{u}}\right)", "Usada quando a base e o expoente podem depender da variavel."))
            self._walk_derivative(expr.base, var, steps, depth + 1)
        elif isinstance(expr, Sin):
            steps.append(CalculationStep("Regra do seno com cadeia", fr"\frac{{d}}{{d{var.to_latex()}}}\sin(u)=\cos(u)u'", f"Aqui u={expr.arg.to_latex()}."))
            self._walk_derivative(expr.arg, var, steps, depth + 1)
        elif isinstance(expr, Cos):
            steps.append(CalculationStep("Regra do cosseno com cadeia", fr"\frac{{d}}{{d{var.to_latex()}}}\cos(u)=-\sin(u)u'", f"Aqui u={expr.arg.to_latex()}."))
            self._walk_derivative(expr.arg, var, steps, depth + 1)
        elif isinstance(expr, Exp):
            steps.append(CalculationStep("Regra da exponencial com cadeia", fr"\frac{{d}}{{d{var.to_latex()}}}e^u=e^u u'", f"Aqui u={expr.arg.to_latex()}."))
            self._walk_derivative(expr.arg, var, steps, depth + 1)
        elif isinstance(expr, Log):
            steps.append(CalculationStep("Regra do logaritmo com cadeia", fr"\frac{{d}}{{d{var.to_latex()}}}\log(u)=\frac{{u'}}{{u}}", f"Aqui u={expr.arg.to_latex()}."))
            self._walk_derivative(expr.arg, var, steps, depth + 1)
        elif isinstance(expr, Sqrt):
            steps.append(CalculationStep("Regra da raiz com cadeia", fr"\frac{{d}}{{d{var.to_latex()}}}\sqrt{{u}}=\frac{{u'}}{{2\sqrt{{u}}}}", f"Aqui u={expr.arg.to_latex()}."))
            self._walk_derivative(expr.arg, var, steps, depth + 1)


class ExtremePDFReport:
    """PDF report builder for NablaMath scientific/math reports."""

    def __init__(self, title: str, output_path: str | Path, author: str = "NablaMath", temp_dir: Optional[str | Path] = None):
        self.title = title
        self.output_path = Path(output_path)
        self.author = author
        self.sections: List[ReportSection] = []
        self.metadata: Dict[str, Any] = {"created_at_unix": time.time(), "generator": "NablaMath ExtremePDFReport"}
        self.temp_dir = Path(temp_dir) if temp_dir else self.output_path.parent / "_report_assets"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.eq_renderer = LatexEquationRenderer(self.temp_dir)

    def add_section(self, section: ReportSection) -> "ExtremePDFReport":
        self.sections.append(section)
        return self

    def build(self) -> Path:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle("NablaTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=22, leading=26, spaceAfter=14))
        styles.add(ParagraphStyle("NablaH1", parent=styles["Heading1"], fontSize=16, leading=20, spaceBefore=12, spaceAfter=8))
        styles.add(ParagraphStyle("NablaH2", parent=styles["Heading2"], fontSize=13, leading=16, spaceBefore=8, spaceAfter=5))
        styles.add(ParagraphStyle("NablaBody", parent=styles["BodyText"], fontSize=9.5, leading=13, alignment=TA_LEFT, spaceAfter=6))
        styles.add(ParagraphStyle("NablaSmall", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#444444")))

        doc = SimpleDocTemplate(str(self.output_path), pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.4*cm, bottomMargin=1.3*cm,
                                title=self.title, author=self.author)
        story: List[Any] = []
        story.append(Paragraph(self.title, styles["NablaTitle"]))
        story.append(Paragraph("Relatorio extremo com calculos simbolicos, derivacoes passo a passo, LaTeX renderizado, diagnosticos numericos e metadados reprodutiveis.", styles["NablaBody"]))
        meta_rows = [["Campo", "Valor"]] + [[k, str(v)] for k, v in self.metadata.items()]
        story.append(_reportlab_table(meta_rows, styles))
        story.append(Spacer(1, 0.3*cm))

        for idx, section in enumerate(self.sections, start=1):
            story.append(Paragraph(f"{idx}. {section.title}", styles["NablaH1"]))
            for p in section.paragraphs:
                story.append(Paragraph(_escape(str(p)), styles["NablaBody"]))
            for step_i, step in enumerate(section.steps, start=1):
                story.append(Paragraph(f"{idx}.{step_i} {step.title}", styles["NablaH2"]))
                if step.explanation:
                    story.append(Paragraph(_escape(step.explanation), styles["NablaBody"]))
                if step.latex:
                    eq_path = self.eq_renderer.render(step.latex)
                    if eq_path:
                        story.append(Image(str(eq_path), width=min(16*cm, 0.80*16*cm), height=None, kind="proportional"))
                    else:
                        story.append(Paragraph(_escape(step.latex), styles["NablaSmall"]))
                if step.result_latex:
                    story.append(Paragraph("Resultado:", styles["NablaSmall"]))
                    eq_path = self.eq_renderer.render(step.result_latex, fontsize=16)
                    if eq_path:
                        story.append(Image(str(eq_path), width=min(15*cm, 0.80*15*cm), height=None, kind="proportional"))
                    else:
                        story.append(Paragraph(_escape(step.result_latex), styles["NablaSmall"]))
            for headers, rows in section.tables:
                story.append(_reportlab_table([headers] + rows, styles))
            for asset in section.assets:
                if asset.path.exists():
                    story.append(Image(str(asset.path), width=16*cm, height=None, kind="proportional"))
                    if asset.caption:
                        story.append(Paragraph(_escape(asset.caption), styles["NablaSmall"]))
            story.append(Spacer(1, 0.2*cm))

        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        return self.output_path


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.drawString(36, 20, "NablaMath v0.3 - generated scientific report")
    canvas.drawRightString(560, 20, f"Page {doc.page}")
    canvas.restoreState()


def _reportlab_table(rows: List[List[Any]], styles: Any) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle
    body = [[Paragraph(_escape(str(cell)), styles["NablaSmall"]) for cell in row] for row in rows]
    table = Table(body, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BBBBBB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def build_function_report(expr: Expr, variables: Sequence[Symbol], output_path: str | Path,
                          start: Optional[Mapping[str, float]] = None,
                          bounds: Optional[Mapping[str, Tuple[float, float]]] = None,
                          visual_assets: Optional[Iterable[str | Path]] = None) -> Path:
    """Generate a complete PDF report for a symbolic function."""
    deriver = StepByStepDeriver()
    report = ExtremePDFReport("NablaMath v0.3 - Relatorio matematico extremo", output_path)
    report.metadata.update({
        "expression": str(expr),
        "latex": expr.to_latex(),
        "variables": ", ".join(v.name for v in variables),
    })

    intro = ReportSection(
        title="Objeto matematico analisado",
        paragraphs=[
            "Este relatorio foi gerado automaticamente pela NablaMath. Ele combina representacao simbolica, renderizacao LaTeX, derivacoes passo a passo, analise numerica, otimizacao e ativos visuais exportados.",
            "A expressao e tratada como arvore simbolica, permitindo derivacao exata e avaliacao numerica posterior.",
        ],
        steps=[CalculationStep("Expressao original", latex=fr"f={expr.to_latex()}", explanation="Forma em LaTeX da expressao fornecida.")],
    )
    report.add_section(intro)

    grad_section = ReportSection(title="Gradiente e derivadas parciais passo a passo")
    grad_section.steps.extend(deriver.gradient_steps(expr, variables))
    report.add_section(grad_section)

    hess_section = ReportSection(title="Hessiana e curvatura local")
    hess_section.steps.extend(deriver.hessian_steps(expr, variables))
    report.add_section(hess_section)

    numeric_section = ReportSection(title="Diagnostico numerico e otimizacao")
    if start is not None:
        vals = dict(start)
        numeric_section.steps.append(CalculationStep("Avaliacao no ponto inicial", latex=fr"f({', '.join(str(vals.get(v.name, '?')) for v in variables)})={expr.eval(vals):.8g}", explanation="Valor numerico da funcao no ponto inicial."))
        try:
            gd = gradient_descent(expr, variables, dict(start), lr=0.01, steps=80)
            numeric_section.tables.append((["Metodo", "Melhor valor", "Melhor ponto", "Iteracoes"], [["Gradient Descent", f"{gd.best_value:.8g}", str(gd.best_point), len(gd.values)]]))
        except Exception as exc:
            numeric_section.paragraphs.append(f"Gradient descent falhou: {exc}")
        try:
            adam = adam_optimize(expr, variables, dict(start), lr=0.05, steps=120)
            numeric_section.tables.append((["Metodo", "Melhor valor", "Melhor ponto", "Iteracoes"], [["Adam", f"{adam.best_value:.8g}", str(adam.best_point), len(adam.values)]]))
        except Exception as exc:
            numeric_section.paragraphs.append(f"Adam falhou: {exc}")
    if bounds is not None:
        try:
            rs = random_search(expr, variables, bounds, samples=400, seed=42)
            numeric_section.tables.append((["Metodo", "Melhor valor", "Melhor ponto", "Amostras"], [["Random Search", f"{rs.best_value:.8g}", str(rs.best_point), len(rs.values)]]))
        except Exception as exc:
            numeric_section.paragraphs.append(f"Random search falhou: {exc}")
    report.add_section(numeric_section)

    if visual_assets:
        assets = [ReportAsset(Path(p), caption=f"Ativo visual: {Path(p).name}") for p in visual_assets]
        report.add_section(ReportSection(title="Visualizacoes cientificas anexadas", paragraphs=["Esta secao incorpora figuras exportadas pelo modulo de visualizacao."], assets=assets))

    return report.build()
