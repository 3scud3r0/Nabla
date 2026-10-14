#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NablaMath All Modules LaTeX Professional - single-file edition.

This file contains three professional modules:

1. RelativityModule
   - special relativity derivations
   - general relativity derivations
   - figures, tables, calculation ledgers and appendices

2. OrbitalModule
   - orbital mechanics
   - deorbit, reentry, heat flux, pressure, plasma, blackout
   - wind-tunnel surrogate and geometry notes
   - figures, tables, calculation ledgers and appendices

3. ExhaustiveCalculatorModule
   - symbolic/numeric step-by-step calculation reports
   - quadratic, derivative, integral, matrix, uncertainty propagation

The PDF pipeline intentionally uses real LaTeX and pdflatex. It does not use a
simplified ReportLab-only layout for mathematical documents.

Quick usage:

    python NablaMath_All_Modules_LaTeX_Professional.py --out outputs --rel-pages 120 --orb-pages 100 --calc-pages 60

Light test:

    python NablaMath_All_Modules_LaTeX_Professional.py --out outputs_test --rel-pages 45 --orb-pages 40 --calc-pages 20

Generated:
    outputs/relativity/NablaMath_Relativity_Professional_Report.pdf
    outputs/orbital/NablaMath_Orbital_Professional_Report.pdf
    outputs/calculator/NablaMath_Calculator_Professional_Report.pdf
    outputs/combined/NablaMath_Combined_Relativity_Orbital_Calculator.pdf
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import textwrap
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover
    plt = None

# =============================================================================
# Global physical constants
# =============================================================================

C = 299_792_458.0
G = 6.67430e-11
G0 = 9.80665
M_EARTH = 5.97219e24
R_EARTH = 6_371_000.0
MU_EARTH = G * M_EARTH
R_AIR = 287.05
GAMMA_AIR = 1.4
SIGMA_SB = 5.670374419e-8
M_AIR = 4.81e-26

# =============================================================================
# Utility layer: filesystem, LaTeX, PDF compilation, report builder
# =============================================================================


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def tex_escape(text: Any) -> str:
    """Escape text for LaTeX non-math contexts."""
    s = str(text)
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
    return "".join(repl.get(ch, ch) for ch in s)


def safe_number(x: float, digits: int = 6) -> str:
    if not math.isfinite(float(x)):
        return "nan"
    if abs(x) >= 1e4 or (abs(x) < 1e-3 and x != 0):
        return f"{x:.{digits}e}"
    return f"{x:.{digits}f}"


def run_pdflatex(tex_path: Path, runs: int = 2, timeout: int = 240) -> Tuple[Optional[Path], Path, bool, str]:
    pdflatex = shutil.which("pdflatex")
    log_path = tex_path.with_suffix(".compile.log")
    if not pdflatex:
        log_path.write_text("pdflatex not found. TeX generated only.\n", encoding="utf-8")
        return None, log_path, False, "pdflatex not found"

    combined = []
    ok = True
    for i in range(runs):
        proc = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
            cwd=str(tex_path.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        combined.append(f"\n--- pdflatex run {i+1} ---\n{proc.stdout}")
        if proc.returncode != 0:
            ok = False
            break
    log_path.write_text("\n".join(combined), encoding="utf-8", errors="replace")
    pdf_path = tex_path.with_suffix(".pdf")
    if ok and pdf_path.exists() and pdf_path.stat().st_size > 0:
        return pdf_path, log_path, True, "compiled"
    return None, log_path, False, "pdflatex failed"


def merge_pdfs(pdf_paths: Sequence[Path], output_path: Path) -> bool:
    """Merge PDFs using PyPDF2/pypdf if available."""
    try:
        try:
            from pypdf import PdfWriter
        except Exception:
            from PyPDF2 import PdfWriter
        writer = PdfWriter()
        for p in pdf_paths:
            if p and p.exists():
                writer.append(str(p))
        with output_path.open("wb") as f:
            writer.write(f)
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception:
        return False


@dataclass
class PDFBuildResult:
    tex_path: Path
    pdf_path: Optional[Path]
    log_path: Path
    success: bool
    message: str
    assets: Dict[str, str] = field(default_factory=dict)


class LatexDocument:
    def __init__(self, title: str, author: str, output_dir: Path, filename: str):
        self.title = title
        self.author = author
        self.output_dir = ensure_dir(output_dir)
        self.filename = filename
        self.parts: List[str] = []
        self.assets: Dict[str, str] = {}

    def add(self, latex: str) -> None:
        self.parts.append(textwrap.dedent(latex).strip() + "\n")

    def figure(self, image_path: Path, caption: str, width: str = "0.92\\textwidth") -> str:
        self.assets[image_path.stem] = str(image_path)
        return textwrap.dedent(f"""
        \\begin{{figure}}[H]
        \\centering
        \\includegraphics[width={width}]{{{image_path.name}}}
        \\caption{{{tex_escape(caption)}}}
        \\end{{figure}}
        """)

    def header(self) -> str:
        return textwrap.dedent(fr"""
        \documentclass[11pt,a4paper]{{article}}
        \usepackage[utf8]{{inputenc}}
        \usepackage[T1]{{fontenc}}
        \usepackage{{lmodern}}
        \usepackage{{microtype}}
        \usepackage{{amsmath,amssymb,amsfonts,mathtools,bm}}
        \usepackage{{physics}}
        \usepackage{{geometry}}
        \usepackage{{booktabs,longtable,array,multirow}}
        \usepackage{{graphicx,float}}
        \usepackage{{xcolor}}
        \usepackage{{hyperref}}
        \usepackage{{fancyhdr}}
        \usepackage{{listings}}
        \usepackage{{tcolorbox}}
        \usepackage{{enumitem}}
        \usepackage{{caption}}
        \geometry{{margin=1.35cm}}
        \hypersetup{{colorlinks=true, linkcolor=blue!55!black, urlcolor=blue!60!black, citecolor=blue!60!black}}
        \pagestyle{{fancy}}
        \fancyhf{{}}
        \lhead{{NablaMath Professional LaTeX Engine}}
        \rhead{{\leftmark}}
        \cfoot{{\thepage}}
        \setlength{{\parskip}}{{0.45em}}
        \setlength{{\parindent}}{{0pt}}
        \lstdefinestyle{{nabla}}{{
          basicstyle=\ttfamily\small,
          backgroundcolor=\color{{black!3}},
          frame=single,
          breaklines=true,
          keywordstyle=\color{{blue!70!black}},
          commentstyle=\color{{green!40!black}},
          stringstyle=\color{{red!50!black}},
          showstringspaces=false,
          columns=fullflexible
        }}
        \newtcolorbox{{derivationbox}}{{colback=blue!2!white,colframe=blue!45!black,title=Derivation}}
        \newtcolorbox{{resultbox}}{{colback=green!2!white,colframe=green!45!black,title=Result}}
        \newtcolorbox{{warningbox}}{{colback=orange!3!white,colframe=orange!60!black,title=Model scope}}
        \title{{{tex_escape(self.title)}}}
        \author{{{tex_escape(self.author)}}}
        \date{{\today}}
        \begin{{document}}
        \maketitle
        \begin{{abstract}}
        This document was generated by a single-file NablaMath professional module. The report intentionally uses real LaTeX for mathematical derivations, equations, tables, figures, appendices, and reproducibility metadata. It is designed as a template for producing long technical dossiers, including hundreds of pages when requested.
        \end{{abstract}}
        \tableofcontents
        \newpage
        """)

    def footer(self) -> str:
        return "\n\\end{document}\n"

    def write_tex(self) -> Path:
        tex_path = self.output_dir / f"{self.filename}.tex"
        tex_path.write_text(self.header() + "\n".join(self.parts) + self.footer(), encoding="utf-8")
        return tex_path

    def build_pdf(self, runs: int = 2) -> PDFBuildResult:
        tex_path = self.write_tex()
        pdf_path, log_path, ok, msg = run_pdflatex(tex_path, runs=runs)
        return PDFBuildResult(tex_path=tex_path, pdf_path=pdf_path, log_path=log_path, success=ok, message=msg, assets=self.assets)

# =============================================================================
# Exhaustive calculator module
# =============================================================================

@dataclass
class CalculationStep:
    title: str
    latex: str
    explanation: str
    numeric_result: Optional[str] = None


class ExhaustiveCalculatorModule:
    """Generate step-by-step calculations rendered as real LaTeX."""

    def quadratic_steps(self, a: float, b: float, c_: float) -> List[CalculationStep]:
        D = b*b - 4*a*c_
        sqrtD = math.sqrt(D) if D >= 0 else float("nan")
        x1 = (-b + sqrtD)/(2*a) if D >= 0 else float("nan")
        x2 = (-b - sqrtD)/(2*a) if D >= 0 else float("nan")
        return [
            CalculationStep("Original equation", fr"{a}x^2 + {b}x + {c_} = 0", "Identify coefficients."),
            CalculationStep("Discriminant", fr"\Delta=b^2-4ac=({b})^2-4({a})({c_})={D}", "The discriminant determines the number and type of roots."),
            CalculationStep("Quadratic formula", fr"x=\frac{{-b\pm\sqrt{{\Delta}}}}{{2a}}=\frac{{{-b}\pm\sqrt{{{D}}}}}{{{2*a}}}", "Substitute the discriminant into the closed form."),
            CalculationStep("Roots", fr"x_1={safe_number(x1)},\qquad x_2={safe_number(x2)}", "Final roots.", f"x1={x1}, x2={x2}"),
        ]

    def derivative_steps(self) -> List[CalculationStep]:
        return [
            CalculationStep("Function", r"f(x)=x^4-3x^3+2x^2-7x+5", "Polynomial derivative example."),
            CalculationStep("Linearity", r"\dv{x}\left(x^4-3x^3+2x^2-7x+5\right)=\dv{x}x^4-3\dv{x}x^3+2\dv{x}x^2-7\dv{x}x+\dv{x}5", "Derivative distributes over addition."),
            CalculationStep("Power rule", r"\dv{x}x^n=nx^{n-1}", "Apply the power rule term by term."),
            CalculationStep("Final derivative", r"f'(x)=4x^3-9x^2+4x-7", "Simplified derivative."),
            CalculationStep("Second derivative", r"f''(x)=12x^2-18x+4", "Apply derivative again."),
        ]

    def integral_steps(self) -> List[CalculationStep]:
        return [
            CalculationStep("Integral", r"I=\int_0^1 (3x^2+2x+1)\,dx", "Definite polynomial integral."),
            CalculationStep("Antiderivative", r"\int (3x^2+2x+1)\,dx=x^3+x^2+x+C", "Integrate term by term."),
            CalculationStep("Fundamental theorem", r"I=\left[x^3+x^2+x\right]_0^1=(1+1+1)-0=3", "Evaluate endpoint difference."),
        ]

    def matrix_steps(self) -> List[CalculationStep]:
        A = np.array([[2, 1], [3, 4]], dtype=float)
        B = np.array([[5, -1], [2, 0]], dtype=float)
        Cmat = A @ B
        return [
            CalculationStep("Matrices", r"A=\begin{bmatrix}2&1\\3&4\end{bmatrix},\quad B=\begin{bmatrix}5&-1\\2&0\end{bmatrix}", "Define matrices."),
            CalculationStep("Product definition", r"(AB)_{ij}=\sum_{k=1}^{2}A_{ik}B_{kj}", "Matrix multiplication rule."),
            CalculationStep("Element calculation", r"(AB)_{11}=2\cdot5+1\cdot2=12,\quad (AB)_{12}=2(-1)+1(0)=-2", "First row calculations."),
            CalculationStep("Element calculation", r"(AB)_{21}=3\cdot5+4\cdot2=23,\quad (AB)_{22}=3(-1)+4(0)=-3", "Second row calculations."),
            CalculationStep("Result", r"AB=\begin{bmatrix}12&-2\\23&-3\end{bmatrix}", "Final product.", str(Cmat)),
        ]

    def uncertainty_steps(self) -> List[CalculationStep]:
        return [
            CalculationStep("Function", r"y=x^2z,\quad x=3.0\pm0.1,\quad z=5.0\pm0.2", "Propagate independent uncertainty."),
            CalculationStep("Partial derivatives", r"\pdv{y}{x}=2xz,\qquad \pdv{y}{z}=x^2", "Linear error propagation uses local sensitivity."),
            CalculationStep("Variance propagation", r"\sigma_y^2=\left(\pdv{y}{x}\sigma_x\right)^2+\left(\pdv{y}{z}\sigma_z\right)^2", "Independent variables, no covariance."),
            CalculationStep("Substitution", r"\sigma_y^2=(2\cdot3\cdot5\cdot0.1)^2+(3^2\cdot0.2)^2=3^2+1.8^2=12.24", "Numeric substitution."),
            CalculationStep("Final", r"y=45.0,\qquad \sigma_y=\sqrt{12.24}\approx3.50", "Reported as value plus uncertainty."),
        ]

    def build_report(self, output_dir: Path, pages_target: int = 40) -> PDFBuildResult:
        doc = LatexDocument(
            title="NablaMath Exhaustive Calculator Module - Step-by-Step Rendered Calculations",
            author="NablaMath All-in-One Professional Engine",
            output_dir=output_dir,
            filename="NablaMath_Calculator_Professional_Report",
        )
        doc.add(r"""
        \section{Module purpose}
        The calculator module converts a computational problem into a traceable sequence of mathematical steps. Each step includes a displayed LaTeX equation, the local rule used, and the final numerical result when applicable.
        """)
        cases = [
            ("Quadratic calculation", self.quadratic_steps(2, -7, 3)),
            ("Polynomial derivative", self.derivative_steps()),
            ("Polynomial integral", self.integral_steps()),
            ("Matrix multiplication", self.matrix_steps()),
            ("Uncertainty propagation", self.uncertainty_steps()),
        ]
        for title, steps in cases:
            doc.add(fr"\section{{{tex_escape(title)}}}")
            for step in steps:
                doc.add(fr"""
                \subsection{{{tex_escape(step.title)}}}
                {tex_escape(step.explanation)}
                \begin{{derivationbox}}
                \[
                {step.latex}
                \]
                \end{{derivationbox}}
                """)
                if step.numeric_result:
                    doc.add(fr"\begin{{resultbox}} {tex_escape(step.numeric_result)} \end{{resultbox}}")
        self._append_calculation_ledger(doc, pages_target)
        return doc.build_pdf()

    def _append_calculation_ledger(self, doc: LatexDocument, pages_target: int) -> None:
        doc.add(r"\section{Extended calculation ledger}")
        n_sections = max(3, pages_target // 5)
        for k in range(1, n_sections + 1):
            a = 1 + (k % 5)
            b = -2.0 - 0.35*k
            c0 = 0.1*k
            D = b*b - 4*a*c0
            doc.add(fr"""
            \subsection{{Ledger case {k}: quadratic audit}}
            \begin{{align}}
            a &= {a}, & b &= {safe_number(b)}, & c &= {safe_number(c0)} \\
            \Delta &= b^2-4ac = ({safe_number(b)})^2 - 4({a})({safe_number(c0)}) = {safe_number(D)}
            \end{{align}}
            """)
            if D >= 0:
                x1 = (-b + math.sqrt(D))/(2*a)
                x2 = (-b - math.sqrt(D))/(2*a)
                doc.add(fr"""
                \begin{{align}}
                x_1 &= \frac{{-b+\sqrt{{\Delta}}}}{{2a}} = {safe_number(x1)} \\
                x_2 &= \frac{{-b-\sqrt{{\Delta}}}}{{2a}} = {safe_number(x2)}
                \end{{align}}
                """)
            else:
                doc.add(r"\[\Delta<0\Rightarrow \text{complex roots.}\]")
            if k % 3 == 0:
                doc.add(r"\newpage")

# =============================================================================
# Relativity module
# =============================================================================

class RelativityModule:
    def __init__(self, output_dir: Path):
        self.output_dir = ensure_dir(output_dir)
        self.fig_dir = ensure_dir(self.output_dir / "figures")

    def create_figures(self) -> Dict[str, Path]:
        figs: Dict[str, Path] = {}
        if plt is None:
            return figs
        beta = np.linspace(0, 0.995, 600)
        gamma = 1.0 / np.sqrt(1.0 - beta**2)
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(beta, gamma)
        ax.set_xlabel(r"$\beta=v/c$")
        ax.set_ylabel(r"$\gamma=(1-\beta^2)^{-1/2}$")
        ax.set_title("Lorentz factor")
        ax.grid(True, alpha=0.3)
        p = self.fig_dir / "lorentz_factor.png"
        fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); figs["lorentz_factor"] = p

        fig, ax = plt.subplots(figsize=(6, 6))
        x = np.linspace(-1, 1, 300)
        ax.plot(x, x, label=r"$ct=x$")
        ax.plot(x, -x, label=r"$ct=-x$")
        ax.fill_between(x, np.abs(x), 1, alpha=0.08)
        ax.fill_between(x, -np.abs(x), np.abs(x), alpha=0.15)
        ax.set_xlabel(r"$x$")
        ax.set_ylabel(r"$ct$")
        ax.set_title("Light cone in 1+1 spacetime")
        ax.set_xlim(-1, 1); ax.set_ylim(-1, 1)
        ax.legend(); ax.grid(True, alpha=0.3)
        p = self.fig_dir / "light_cone.png"
        fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); figs["light_cone"] = p

        r = np.linspace(2.2, 20, 600)
        rs = 2.0
        redshift = 1.0/np.sqrt(1.0 - rs/r) - 1.0
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(r/rs, redshift)
        ax.set_xlabel(r"$r/r_s$")
        ax.set_ylabel(r"$z=(1-r_s/r)^{-1/2}-1$")
        ax.set_title("Schwarzschild gravitational redshift")
        ax.grid(True, alpha=0.3)
        p = self.fig_dir / "schwarzschild_redshift.png"
        fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); figs["redshift"] = p

        theta = np.linspace(0, 12*np.pi, 2200)
        e = 0.35
        precession = 0.025
        rr = 1.0 / (1.0 + e*np.cos((1.0 - precession)*theta))
        fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"projection": "polar"})
        ax.plot(theta, rr)
        ax.set_title("Precessing orbit schematic")
        p = self.fig_dir / "precessing_orbit.png"
        fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); figs["precession"] = p
        return figs

    def build_report(self, pages_target: int = 100) -> PDFBuildResult:
        figs = self.create_figures()
        for p in figs.values():
            shutil.copy2(p, self.output_dir / p.name)
        doc = LatexDocument(
            title="NablaMath Relativity Module - Complete Professional Derivation Report",
            author="NablaMath All-in-One Professional Engine",
            output_dir=self.output_dir,
            filename="NablaMath_Relativity_Professional_Report",
        )
        self._intro(doc)
        self._special_relativity(doc)
        if "lorentz_factor" in figs:
            doc.add(doc.figure(self.output_dir / figs["lorentz_factor"].name, "Lorentz factor growth as velocity approaches c."))
        if "light_cone" in figs:
            doc.add(doc.figure(self.output_dir / figs["light_cone"].name, "Causal structure of flat spacetime in 1+1 dimensions.", width="0.65\\textwidth"))
        self._general_relativity(doc)
        if "redshift" in figs:
            doc.add(doc.figure(self.output_dir / figs["redshift"].name, "Schwarzschild gravitational redshift."))
        if "precession" in figs:
            doc.add(doc.figure(self.output_dir / figs["precession"].name, "Schematic relativistic periapsis precession.", width="0.65\\textwidth"))
        self._append_relativity_ledger(doc, pages_target)
        return doc.build_pdf()

    def _intro(self, doc: LatexDocument) -> None:
        doc.add(r"""
        \section{Objective and structure}
        This module is designed to generate long-form relativity reports. It is not a short summary. It preserves assumptions, derives equations step by step, produces tables and figures, and exposes a configurable appendix generator for hundreds of pages.
        \begin{warningbox}
        The report is pedagogical and symbolic. It is not a substitute for a full numerical relativity code such as BSSN/ADM solvers, but it provides a rigorous derivation scaffold for special and general relativity.
        \end{warningbox}
        """)

    def _special_relativity(self, doc: LatexDocument) -> None:
        doc.add(r"""
        \part{Special Relativity}
        \section{Postulates}
        \begin{enumerate}[label=\textbf{P\arabic*.}]
        \item The laws of physics are identical in all inertial frames.
        \item The vacuum speed of light is invariant and equal to $c$ in all inertial frames.
        \end{enumerate}
        Let $S$ and $S'$ be inertial frames, with $S'$ moving at velocity $v$ along the $x$ axis relative to $S$.

        \section{Linearity of transformations}
        Homogeneity of space and time implies a linear coordinate map:
        \begin{align}
        x' &= A x + B t, \\
        t' &= D x + E t.
        \end{align}
        The origin of $S'$ satisfies $x'=0$ and moves as $x=vt$. Hence
        \begin{align}
        0=A(vt)+Bt \Rightarrow B=-Av,
        \end{align}
        giving
        \begin{align}
        x'=A(x-vt).
        \end{align}
        By symmetry the inverse must have the same form with $v\to -v$:
        \begin{align}
        x=A(x'+vt').
        \end{align}

        \section{Light invariance and Lorentz factor}
        Light moving along $+x$ obeys $x=ct$ and $x'=ct'$. Light moving along $-x$ obeys $x=-ct$ and $x'=-ct'$. The interval condition is
        \begin{align}
        c^2t'^2-x'^2=c^2t^2-x^2.
        \end{align}
        Substitute the ansatz $x'=A(x-vt)$ and solve for $t'$ by requiring interval preservation:
        \begin{derivationbox}
        \begin{align}
        x'&=\gamma(x-vt),\\
        ct'&=\gamma\left(ct-\frac{v}{c}x\right),\\
        t'&=\gamma\left(t-\frac{vx}{c^2}\right),\\
        \gamma&=\frac{1}{\sqrt{1-v^2/c^2}}.
        \end{align}
        \end{derivationbox}
        Therefore the Lorentz transformation is
        \begin{resultbox}
        \begin{align}
        x'&=\gamma(x-vt),\\
        y'&=y,\\
        z'&=z,\\
        t'&=\gamma\left(t-\frac{vx}{c^2}\right).
        \end{align}
        \end{resultbox}

        \section{Time dilation}
        A clock at rest in $S'$ has $\Delta x'=0$. From inverse Lorentz transformation,
        \begin{align}
        \Delta t=\gamma\left(\Delta t'+\frac{v\Delta x'}{c^2}\right)=\gamma\Delta t'.
        \end{align}
        If $\Delta\tau=\Delta t'$ is proper time, then
        \begin{resultbox}
        \[
        \Delta t=\gamma\Delta\tau.
        \]
        \end{resultbox}

        \section{Length contraction}
        A rod at rest in $S'$ has proper length $L_0=\Delta x'$. Its length in $S$ is measured simultaneously, so $\Delta t=0$:
        \begin{align}
        \Delta x' &= \gamma(\Delta x-v\Delta t)=\gamma\Delta x.
        \end{align}
        Thus
        \begin{resultbox}
        \[
        L=\Delta x=\frac{L_0}{\gamma}.
        \]
        \end{resultbox}

        \section{Relativistic velocity addition}
        Let $u=dx/dt$ and $u'=dx'/dt'$. Then
        \begin{align}
        u' &= \frac{dx'}{dt'}
        =\frac{\gamma(dx-vdt)}{\gamma(dt-vdx/c^2)}
        =\frac{u-v}{1-uv/c^2}.
        \end{align}
        The inverse is
        \[
        u=\frac{u'+v}{1+u'v/c^2}.
        \]

        \section{Four-vectors and invariant interval}
        Define the spacetime coordinate
        \[
        x^\mu=(ct,x,y,z).
        \]
        With metric signature $(-,+,+,+)$,
        \begin{align}
        ds^2 &= \eta_{\mu\nu}dx^\mu dx^\nu \\
             &= -c^2dt^2+dx^2+dy^2+dz^2.
        \end{align}
        Timelike proper time satisfies
        \begin{align}
        d\tau^2 = dt^2-\frac{1}{c^2}(dx^2+dy^2+dz^2).
        \end{align}

        \section{Energy and momentum}
        Four-velocity is
        \begin{align}
        U^\mu=\dv{x^\mu}{\tau}=\gamma(c,\mathbf{v}).
        \end{align}
        Four-momentum is
        \begin{align}
        p^\mu=mU^\mu=(\gamma mc,\gamma m\mathbf{v}).
        \end{align}
        Define
        \begin{align}
        E=\gamma mc^2,\qquad \mathbf{p}=\gamma m\mathbf{v}.
        \end{align}
        The invariant norm becomes
        \begin{align}
        p_\mu p^\mu&=-m^2c^2,\\
        -\frac{E^2}{c^2}+p^2&=-m^2c^2,\\
        E^2&=p^2c^2+m^2c^4.
        \end{align}
        At rest $p=0$, so
        \begin{resultbox}
        \[
        E_0=mc^2.
        \]
        \end{resultbox}
        """)

    def _general_relativity(self, doc: LatexDocument) -> None:
        doc.add(r"""
        \part{General Relativity}
        \section{Equivalence principle}
        Locally, a uniform gravitational field is indistinguishable from acceleration. This motivates replacing gravitational force by geometry: free particles follow geodesics in curved spacetime.

        \section{Metric tensor}
        The invariant interval generalizes from
        \[
        ds^2=\eta_{\mu\nu}dx^\mu dx^\nu
        \]
        to
        \begin{resultbox}
        \[
        ds^2=g_{\mu\nu}(x)dx^\mu dx^\nu.
        \]
        \end{resultbox}
        The metric contains local clock rates, rulers, causal cones, and gravitational potentials.

        \section{Christoffel symbols}
        The Levi-Civita connection is torsion-free and metric-compatible:
        \begin{align}
        \nabla_\lambda g_{\mu\nu}=0,\qquad \Gamma^\rho_{\mu\nu}=\Gamma^\rho_{\nu\mu}.
        \end{align}
        Solving these conditions gives
        \begin{derivationbox}
        \[
        \Gamma^\rho_{\mu\nu}=\frac{1}{2}g^{\rho\sigma}
        \left(\partial_\mu g_{\nu\sigma}+\partial_\nu g_{\mu\sigma}-\partial_\sigma g_{\mu\nu}\right).
        \]
        \end{derivationbox}

        \section{Geodesic equation from extremal proper time}
        The action for a free massive particle is
        \begin{align}
        S=-mc\int ds=-mc\int \sqrt{-g_{\mu\nu}\dot x^\mu\dot x^\nu}\,d\lambda.
        \end{align}
        The Euler-Lagrange equations lead to
        \begin{resultbox}
        \[
        \dv[2]{x^\rho}{\tau}+\Gamma^\rho_{\mu\nu}\dv{x^\mu}{\tau}\dv{x^\nu}{\tau}=0.
        \]
        \end{resultbox}

        \section{Curvature tensor}
        Curvature measures the non-commutation of covariant derivatives:
        \begin{align}
        [\nabla_\mu,\nabla_\nu]V^\rho=R^\rho{}_{\sigma\mu\nu}V^\sigma.
        \end{align}
        In terms of Christoffel symbols,
        \begin{align}
        R^\rho{}_{\sigma\mu\nu}
        &=\partial_\mu\Gamma^\rho_{\nu\sigma}
        -\partial_\nu\Gamma^\rho_{\mu\sigma}
        +\Gamma^\rho_{\mu\lambda}\Gamma^\lambda_{\nu\sigma}
        -\Gamma^\rho_{\nu\lambda}\Gamma^\lambda_{\mu\sigma}.
        \end{align}
        Contracting indices gives the Ricci tensor and scalar:
        \begin{align}
        R_{\mu\nu}=R^\rho{}_{\mu\rho\nu},\qquad R=g^{\mu\nu}R_{\mu\nu}.
        \end{align}

        \section{Einstein-Hilbert action}
        The gravitational action is
        \begin{align}
        S_g=\frac{c^3}{16\pi G}\int R\sqrt{-g}\,d^4x.
        \end{align}
        Add matter action $S_m$ and vary with respect to $g^{\mu\nu}$:
        \begin{align}
        \delta(S_g+S_m)=0.
        \end{align}
        The variation gives
        \begin{resultbox}
        \[
        R_{\mu\nu}-\frac{1}{2}Rg_{\mu\nu}+\Lambda g_{\mu\nu}=\frac{8\pi G}{c^4}T_{\mu\nu}.
        \]
        \end{resultbox}

        \section{Newtonian limit}
        In weak, static fields,
        \begin{align}
        g_{00}\approx -\left(1+\frac{2\Phi}{c^2}\right).
        \end{align}
        The geodesic equation reduces to
        \begin{align}
        \dv[2]{x^i}{t}\approx -\partial_i\Phi.
        \end{align}
        The $00$ component of Einstein's equation reduces to Poisson's equation:
        \begin{align}
        \nabla^2\Phi=4\pi G\rho.
        \end{align}

        \section{Schwarzschild metric}
        For a static, spherically symmetric vacuum exterior,
        \begin{resultbox}
        \[
        ds^2=-\left(1-\frac{2GM}{rc^2}\right)c^2dt^2+
        \left(1-\frac{2GM}{rc^2}\right)^{-1}dr^2+r^2d\Omega^2.
        \]
        \end{resultbox}
        Define Schwarzschild radius
        \[
        r_s=\frac{2GM}{c^2}.
        \]
        Gravitational redshift for a photon emitted at radius $r$ and received at infinity is
        \begin{align}
        1+z=\left(1-\frac{r_s}{r}\right)^{-1/2}.
        \end{align}

        \section{Perihelion precession}
        The weak-field precession per orbit is
        \begin{resultbox}
        \[
        \Delta\varpi=\frac{6\pi GM}{a(1-e^2)c^2}.
        \]
        \end{resultbox}
        """)

    def _append_relativity_ledger(self, doc: LatexDocument, pages_target: int) -> None:
        doc.add(r"\part{Extended calculation ledger and appendices}")
        sections = max(8, pages_target // 4)
        betas = np.linspace(0.05, 0.995, sections)
        for i, beta in enumerate(betas, start=1):
            gamma = 1.0 / math.sqrt(1.0 - beta*beta)
            v = beta*C
            tau = 1.0
            dil = gamma*tau
            L0 = 10.0
            L = L0/gamma
            E_ratio = gamma
            doc.add(fr"""
            \section{{Relativity ledger case {i}: $\beta={safe_number(beta,4)}$}}
            This ledger entry expands the same derivation numerically, showing how the symbolic equations become computable quantities.
            \begin{{align}}
            \beta &= \frac{{v}}{{c}}={safe_number(beta,6)},\\
            v &= \beta c = {safe_number(v,4)}\,\mathrm{{m/s}},\\
            \gamma &= \frac{{1}}{{\sqrt{{1-\beta^2}}}} = {safe_number(gamma,8)},\\
            \Delta t &= \gamma\Delta\tau = {safe_number(gamma,8)}(1.0\,\mathrm{{s}}) = {safe_number(dil,8)}\,\mathrm{{s}},\\
            L &= \frac{{L_0}}{{\gamma}} = \frac{{10.0\,\mathrm{{m}}}}{{{safe_number(gamma,8)}}} = {safe_number(L,8)}\,\mathrm{{m}},\\
            \frac{{E}}{{mc^2}}&=\gamma={safe_number(E_ratio,8)}.
            \end{{align}}
            """)
            rs_sun = 2*G*1.98847e30/(C*C)
            r_mult = 2.5 + 0.12*i
            redshift = 1.0/math.sqrt(1.0 - 1.0/r_mult) - 1.0
            doc.add(fr"""
            For a Schwarzschild redshift calculation at $r={safe_number(r_mult,4)}r_s$:
            \begin{{align}}
            r_s &= \frac{{2GM_\odot}}{{c^2}}={safe_number(rs_sun,6)}\,\mathrm{{m}},\\
            1+z &= \left(1-\frac{{r_s}}{{r}}\right)^{{-1/2}}
            =\left(1-\frac{{1}}{{{safe_number(r_mult,4)}}}\right)^{{-1/2}},\\
            z&={safe_number(redshift,8)}.
            \end{{align}}
            """)
            if i % 2 == 0:
                doc.add(r"\newpage")

# =============================================================================
# Orbital module
# =============================================================================

@dataclass
class OrbitalMissionConfig:
    mission_name: str = "Asteria-Professional"
    orbit_altitude_m: float = 420_000.0
    perigee_target_m: float = 42_000.0
    entry_altitude_m: float = 122_000.0
    mass_initial_kg: float = 132_000.0
    mass_dry_kg: float = 88_000.0
    reference_area_m2: float = 63.6
    drag_coefficient: float = 1.28
    lift_to_drag: float = 0.22
    nose_radius_m: float = 1.25
    emissivity: float = 0.84
    landing_isp_s: float = 330.0
    landing_burn_start_altitude_m: float = 3000.0
    dt_s: float = 0.5
    max_time_s: float = 5000.0
    communications_frequency_hz: float = 2.25e9


def standard_atmosphere(altitude_m: float) -> Dict[str, float]:
    h = max(0.0, float(altitude_m))
    # Lightweight ISA + exponential continuation.
    if h < 11000:
        T = 288.15 - 0.0065*h
        p = 101325.0*(T/288.15)**(G0/(R_AIR*0.0065))
    elif h < 86000:
        T = 216.65 + 0.001*(h-11000.0)
        p = 22632.06*math.exp(-G0*(h-11000)/(R_AIR*max(T, 1.0)))
    else:
        T = 186.0 + 0.0025*(h-86000.0)
        p86 = 0.3734
        p = p86*math.exp(-(h-86000.0)/7200.0)
    rho = p/(R_AIR*T)
    a = math.sqrt(GAMMA_AIR*R_AIR*T)
    return {"T": T, "p": p, "rho": rho, "a": a}


def circular_orbit(altitude_m: float) -> Dict[str, float]:
    r = R_EARTH + altitude_m
    v = math.sqrt(MU_EARTH/r)
    period = 2*math.pi*math.sqrt(r**3/MU_EARTH)
    return {"r": r, "v": v, "period": period}


def deorbit_delta_v(orbit_altitude_m: float, perigee_altitude_m: float) -> Dict[str, float]:
    ra = R_EARTH + orbit_altitude_m
    rp = R_EARTH + perigee_altitude_m
    at = 0.5*(ra+rp)
    vc = math.sqrt(MU_EARTH/ra)
    va = math.sqrt(MU_EARTH*(2/ra - 1/at))
    vp = math.sqrt(MU_EARTH*(2/rp - 1/at))
    return {"ra": ra, "rp": rp, "a_transfer": at, "v_circ": vc, "v_apogee": va, "delta_v": vc-va, "v_perigee": vp}


def sutton_graves(rho: float, v: float, rn: float) -> float:
    return 1.83e-4*math.sqrt(max(rho, 1e-15)/max(rn, 1e-6))*v**3*1e4


def plasma_frequency(ne_m3: float) -> float:
    return 8980.0*math.sqrt(max(ne_m3, 0.0)/1e6)


class OrbitalModule:
    def __init__(self, output_dir: Path, config: Optional[OrbitalMissionConfig] = None):
        self.output_dir = ensure_dir(output_dir)
        self.fig_dir = ensure_dir(self.output_dir / "figures")
        self.config = config or OrbitalMissionConfig()

    def simulate(self) -> Dict[str, Any]:
        cfg = self.config
        orb = circular_orbit(cfg.orbit_altitude_m)
        deorb = deorbit_delta_v(cfg.orbit_altitude_m, cfg.perigee_target_m)
        at = deorb["a_transfer"]
        r = R_EARTH + cfg.entry_altitude_m
        v = math.sqrt(MU_EARTH*(2/r - 1/at))
        gamma = math.radians(-1.25)
        theta = 0.0
        t = 0.0
        m = cfg.mass_initial_kg
        arrays: Dict[str, List[float]] = {k: [] for k in ["t", "h", "v", "gamma", "downrange", "rho", "p", "T", "mach", "q", "heat", "Twall", "gload", "ion", "ne", "fp"]}
        blackout_start = None
        blackout_end = None
        while r - R_EARTH > cfg.landing_burn_start_altitude_m and t < cfg.max_time_s and v > 100:
            h = r - R_EARTH
            atm = standard_atmosphere(h)
            rho, p, T, a = atm["rho"], atm["p"], atm["T"], atm["a"]
            mach = v/max(a, 1e-9)
            q = 0.5*rho*v*v
            D = q*cfg.drag_coefficient*cfg.reference_area_m2
            L = cfg.lift_to_drag*D
            g = MU_EARTH/(r*r)
            dvdt = -D/m - g*math.sin(gamma)
            dgdt = L/max(m*v, 1e-9) + (v/r - g/max(v,1e-9))*math.cos(gamma)
            drdt = v*math.sin(gamma)
            dtdt = v*math.cos(gamma)/r
            heat = sutton_graves(rho, v, cfg.nose_radius_m)
            Twall = min(4200.0, max(T, (heat/(cfg.emissivity*SIGMA_SB))**0.25))
            ion = min(1.0, (1/(1+math.exp(-(Twall-6200)/900)))*math.sqrt(max(rho,0)/0.02 + 1e-12))
            ne = ion*rho/M_AIR
            fp = plasma_frequency(ne)
            if fp > cfg.communications_frequency_hz and blackout_start is None:
                blackout_start = t
            if fp <= cfg.communications_frequency_hz and blackout_start is not None and blackout_end is None:
                blackout_end = t
            for key, val in [("t",t),("h",h),("v",v),("gamma",math.degrees(gamma)),("downrange",R_EARTH*theta),("rho",rho),("p",p),("T",T),("mach",mach),("q",q),("heat",heat),("Twall",Twall),("gload",abs(dvdt)/G0),("ion",ion),("ne",ne),("fp",fp)]:
                arrays[key].append(float(val))
            v = max(0.0, v + dvdt*cfg.dt_s)
            gamma = gamma + dgdt*cfg.dt_s
            r = max(R_EARTH, r + drdt*cfg.dt_s)
            theta += dtdt*cfg.dt_s
            t += cfg.dt_s
        tl = {k: np.array(vv) for k, vv in arrays.items()}
        landing_v = float(tl["v"][-1]) if len(tl["v"]) else 0.0
        landing_h = float(tl["h"][-1]) if len(tl["h"]) else cfg.landing_burn_start_altitude_m
        landing_dv = landing_v + 35.0
        prop = cfg.mass_initial_kg*(1 - math.exp(-landing_dv/(cfg.landing_isp_s*G0))) if landing_dv > 0 else 0.0
        blackout = 0.0
        if blackout_start is not None:
            blackout = (tl["t"][-1] if blackout_end is None else blackout_end) - blackout_start
        summary = {
            "orbit_velocity": orb["v"], "orbit_period": orb["period"], "deorbit_dv": deorb["delta_v"],
            "entry_velocity": math.sqrt(MU_EARTH*(2/(R_EARTH+cfg.entry_altitude_m)-1/at)),
            "peak_heat": float(np.max(tl["heat"])) if len(tl["heat"]) else 0,
            "peak_q": float(np.max(tl["q"])) if len(tl["q"]) else 0,
            "peak_g": float(np.max(tl["gload"])) if len(tl["gload"]) else 0,
            "peak_Twall": float(np.max(tl["Twall"])) if len(tl["Twall"]) else 0,
            "peak_fp": float(np.max(tl["fp"])) if len(tl["fp"]) else 0,
            "blackout_duration": float(blackout), "landing_propellant": float(prop),
            "landing_start_velocity": landing_v, "landing_start_altitude": landing_h,
        }
        return {"config": asdict(cfg), "orbit": orb, "deorbit": deorb, "timeline": tl, "summary": summary}

    def create_figures(self, sim: Dict[str, Any]) -> Dict[str, Path]:
        figs = {}
        if plt is None:
            return figs
        tl = sim["timeline"]
        fig, axs = plt.subplots(2, 2, figsize=(11, 8))
        axs[0,0].plot(tl["t"], tl["h"]/1000); axs[0,0].set_title("Altitude"); axs[0,0].set_ylabel("km")
        axs[0,1].plot(tl["t"], tl["v"]); axs[0,1].set_title("Velocity"); axs[0,1].set_ylabel("m/s")
        axs[1,0].plot(tl["t"], tl["q"]/1000, label="q kPa"); axs[1,0].plot(tl["t"], tl["heat"]/1e6, label="heat MW/m2"); axs[1,0].legend(); axs[1,0].set_title("Loads")
        axs[1,1].plot(tl["t"], tl["mach"], label="Mach"); axs[1,1].plot(tl["t"], tl["gload"], label="g-load"); axs[1,1].legend(); axs[1,1].set_title("Dynamic state")
        for ax in axs.ravel(): ax.grid(True, alpha=0.3); ax.set_xlabel("time [s]")
        p = self.fig_dir / "orbital_dashboard.png"; fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); figs["dashboard"] = p

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(tl["h"]/1000, tl["Twall"], label="wall temperature")
        ax.plot(tl["h"]/1000, tl["T"], label="ambient temperature")
        ax.set_xlabel("altitude [km]"); ax.set_ylabel("K"); ax.set_title("Thermal profile"); ax.legend(); ax.grid(True, alpha=0.3)
        p = self.fig_dir / "thermal_profile.png"; fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); figs["thermal"] = p

        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(tl["t"], tl["fp"]/1e9, label="plasma frequency [GHz]")
        ax.axhline(self.config.communications_frequency_hz/1e9, color="k", linestyle="--", label="comm link")
        ax.set_xlabel("time [s]"); ax.set_ylabel("GHz"); ax.set_title("Plasma blackout criterion"); ax.legend(); ax.grid(True, alpha=0.3)
        p = self.fig_dir / "plasma_blackout.png"; fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); figs["plasma"] = p

        fig = plt.figure(figsize=(8, 7))
        ax = fig.add_subplot(111, projection="3d")
        down = tl["downrange"] / 1000
        alt = tl["h"] / 1000
        ax.plot(down, np.zeros_like(down), alt)
        ax.scatter(down[::max(1, len(down)//120)], np.zeros_like(down[::max(1, len(down)//120)]), alt[::max(1, len(alt)//120)], c=tl["Twall"][::max(1, len(tl["Twall"])//120)], cmap="inferno", s=8)
        ax.set_xlabel("downrange [km]"); ax.set_ylabel("crossrange [km]"); ax.set_zlabel("altitude [km]"); ax.set_title("3D trajectory schematic")
        p = self.fig_dir / "trajectory3d.png"; fig.tight_layout(); fig.savefig(p, dpi=220); plt.close(fig); figs["trajectory3d"] = p

        return figs

    def build_report(self, pages_target: int = 90) -> PDFBuildResult:
        sim = self.simulate()
        figs = self.create_figures(sim)
        for p in figs.values():
            shutil.copy2(p, self.output_dir / p.name)
        doc = LatexDocument(
            title="NablaMath Orbital Module - Professional Mission, Reentry, Plasma and Thermal Report",
            author="NablaMath All-in-One Professional Engine",
            output_dir=self.output_dir,
            filename="NablaMath_Orbital_Professional_Report",
        )
        self._intro(doc)
        self._equations(doc, sim)
        self._results(doc, sim)
        for key, p in figs.items():
            doc.add(doc.figure(self.output_dir / p.name, f"Orbital module figure: {key}."))
        self._append_orbital_ledger(doc, sim, pages_target)
        return doc.build_pdf()

    def _intro(self, doc: LatexDocument) -> None:
        cfg = self.config
        doc.add(fr"""
        \section{{Mission input and module purpose}}
        The orbital module generates a professional engineering-style report for mission analysis. The user input is represented as a reproducible configuration:
        \begin{{lstlisting}}[style=nabla,language=Python]
OrbitalMissionConfig(
    mission_name={cfg.mission_name!r},
    orbit_altitude_m={cfg.orbit_altitude_m},
    perigee_target_m={cfg.perigee_target_m},
    entry_altitude_m={cfg.entry_altitude_m},
    mass_initial_kg={cfg.mass_initial_kg},
    mass_dry_kg={cfg.mass_dry_kg},
    reference_area_m2={cfg.reference_area_m2},
    drag_coefficient={cfg.drag_coefficient},
    lift_to_drag={cfg.lift_to_drag},
    nose_radius_m={cfg.nose_radius_m},
)
        \end{{lstlisting}}
        """)

    def _equations(self, doc: LatexDocument, sim: Dict[str, Any]) -> None:
        orb, deorb = sim["orbit"], sim["deorbit"]
        doc.add(fr"""
        \section{{Orbital mechanics derivation}}
        For a circular orbit at altitude $h$, the orbital radius is
        \begin{{align}}
        r &= R_E+h = {R_EARTH:.0f}+{self.config.orbit_altitude_m:.0f}={orb['r']:.3f}\,\mathrm{{m}}.
        \end{{align}}
        The circular velocity is derived from centripetal balance:
        \begin{{derivationbox}}
        \begin{{align}}
        \frac{{mv^2}}{{r}} &= \frac{{GM_E m}}{{r^2}},\\
        v^2&=\frac{{GM_E}}{{r}}=\frac{{\mu_E}}{{r}},\\
        v&=\sqrt{{\frac{{\mu_E}}{{r}}}}={orb['v']:.3f}\,\mathrm{{m/s}}.
        \end{{align}}
        \end{{derivationbox}}
        The deorbit transfer is approximated as an ellipse with apogee $r_a$ and perigee $r_p$:
        \begin{{align}}
        a_t &= \frac{{r_a+r_p}}{{2}}={deorb['a_transfer']:.3f}\,\mathrm{{m}},\\
        v_a &= \sqrt{{\mu_E\left(\frac{{2}}{{r_a}}-\frac{{1}}{{a_t}}\right)}}={deorb['v_apogee']:.3f}\,\mathrm{{m/s}},\\
        \Delta v &= v_{{circ}}-v_a={deorb['delta_v']:.3f}\,\mathrm{{m/s}}.
        \end{{align}}
        """)
        doc.add(r"""
        \section{Reentry equations of motion}
        The planar lifting reentry state is $(r,\theta,v,\gamma)$:
        \begin{align}
        \dot r &= v\sin\gamma,\\
        \dot\theta &= \frac{v\cos\gamma}{r},\\
        \dot v &= -\frac{D}{m}-\frac{\mu_E}{r^2}\sin\gamma,\\
        \dot\gamma &= \frac{L}{mv}+\left(\frac{v}{r}-\frac{\mu_E}{vr^2}\right)\cos\gamma.
        \end{align}
        Aerodynamic loads are
        \begin{align}
        q&=\frac12\rho v^2,\\
        D&=qC_DA,\\
        L&=(L/D)D.
        \end{align}
        """)
        doc.add(r"""
        \section{Aerothermal and plasma model}
        The stagnation heat flux is approximated by a Sutton-Graves type relation:
        \begin{align}
        \dot q_{stag} &\approx 1.83\times10^{-4}\sqrt{\frac{\rho}{R_n}}v^3\times10^4.
        \end{align}
        Radiative equilibrium wall temperature is estimated as
        \begin{align}
        T_{wall}&\approx\left(\frac{\dot q}{\epsilon\sigma}\right)^{1/4}.
        \end{align}
        A simple ionization proxy maps wall temperature and density into electron density:
        \begin{align}
        x_{ion}&=\sigma_{logistic}(T_{wall},\rho),\\
        n_e&=x_{ion}\frac{\rho}{m_{air}},\\
        f_p&=8980\sqrt{n_e[\mathrm{cm}^{-3}]}. 
        \end{align}
        A blackout proxy occurs when $f_p$ exceeds the radio link frequency.
        """)

    def _results(self, doc: LatexDocument, sim: Dict[str, Any]) -> None:
        s = sim["summary"]
        doc.add(fr"""
        \section{{Consolidated numeric results}}
        \begin{{longtable}}{{p{{7.0cm}}r}}
        \toprule
        Quantity & Value \\
        \midrule
        Orbit velocity [m/s] & {s['orbit_velocity']:.3f} \\
        Orbit period [s] & {s['orbit_period']:.3f} \\
        Deorbit $\Delta v$ [m/s] & {s['deorbit_dv']:.3f} \\
        Entry velocity [m/s] & {s['entry_velocity']:.3f} \\
        Peak heat flux [W/m$^2$] & {s['peak_heat']:.3e} \\
        Peak dynamic pressure [Pa] & {s['peak_q']:.3e} \\
        Peak g-load [g] & {s['peak_g']:.3f} \\
        Peak wall temperature [K] & {s['peak_Twall']:.3f} \\
        Peak plasma frequency [Hz] & {s['peak_fp']:.3e} \\
        Blackout duration [s] & {s['blackout_duration']:.3f} \\
        Landing propellant proxy [kg] & {s['landing_propellant']:.3f} \\
        \bottomrule
        \end{{longtable}}
        """)

    def _append_orbital_ledger(self, doc: LatexDocument, sim: Dict[str, Any], pages_target: int) -> None:
        doc.add(r"\part{Extended orbital calculation ledger}")
        tl = sim["timeline"]
        n = len(tl["t"])
        entries = max(20, min(n, pages_target * 3))
        idxs = np.linspace(0, n-1, entries).astype(int) if n else []
        chunk = 12
        for block, start in enumerate(range(0, len(idxs), chunk), start=1):
            doc.add(fr"\section{{Trajectory ledger block {block}}}")
            doc.add(r"""
            \begin{longtable}{rrrrrrr}
            \toprule
            $t$ [s] & $h$ [km] & $v$ [m/s] & $M$ & $q$ [kPa] & $\dot q$ [MW/m$^2$] & $T_w$ [K] \\
            \midrule
            """)
            rows = []
            for i in idxs[start:start+chunk]:
                row = "{:.1f} & {:.2f} & {:.1f} & {:.2f} & {:.2f} & {:.3f} & {:.1f}".format(tl["t"][i], tl["h"][i]/1000, tl["v"][i], tl["mach"][i], tl["q"][i]/1000, tl["heat"][i]/1e6, tl["Twall"][i]) + " " + chr(92) + chr(92)
                rows.append(row)
            doc.add("\n".join(rows))
            doc.add(r"""
            \bottomrule
            \end{longtable}
            """)
            doc.add(r"""
            The local quantities in this block are computed from:
            \begin{align}
            q_i &= \frac12\rho_i v_i^2,\\
            D_i &= q_i C_D A,\\
            \dot q_i &\approx 1.83\times10^{-4}\sqrt{\rho_i/R_n}v_i^3\times10^4,\\
            T_{w,i}&\approx(\dot q_i/(\epsilon\sigma))^{1/4}.
            \end{align}
            """)
            if block % 2 == 0:
                doc.add(r"\newpage")

# =============================================================================
# Combined professional generator
# =============================================================================

class NablaMathProfessionalAllModules:
    def __init__(self, output_dir: Path):
        self.output_dir = ensure_dir(output_dir)

    def build_all(self, rel_pages: int, orb_pages: int, calc_pages: int) -> Dict[str, Any]:
        rel_mod = RelativityModule(self.output_dir / "relativity")
        rel_res = rel_mod.build_report(pages_target=rel_pages)

        orb_mod = OrbitalModule(self.output_dir / "orbital")
        orb_res = orb_mod.build_report(pages_target=orb_pages)

        calc_mod = ExhaustiveCalculatorModule()
        calc_res = calc_mod.build_report(self.output_dir / "calculator", pages_target=calc_pages)

        combined_dir = ensure_dir(self.output_dir / "combined")
        combined_pdf = combined_dir / "NablaMath_Combined_Relativity_Orbital_Calculator.pdf"
        pdfs = [p for p in [rel_res.pdf_path, orb_res.pdf_path, calc_res.pdf_path] if p]
        merged = merge_pdfs(pdfs, combined_pdf)

        manifest = {
            "created_at_unix": time.time(),
            "relativity": {"pdf": str(rel_res.pdf_path) if rel_res.pdf_path else None, "tex": str(rel_res.tex_path), "success": rel_res.success},
            "orbital": {"pdf": str(orb_res.pdf_path) if orb_res.pdf_path else None, "tex": str(orb_res.tex_path), "success": orb_res.success},
            "calculator": {"pdf": str(calc_res.pdf_path) if calc_res.pdf_path else None, "tex": str(calc_res.tex_path), "success": calc_res.success},
            "combined_pdf": str(combined_pdf) if merged else None,
            "merged": merged,
        }
        (self.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="NablaMath all modules professional LaTeX generator")
    parser.add_argument("--out", type=str, default="nabla_outputs", help="Output directory")
    parser.add_argument("--rel-pages", type=int, default=80, help="Target scale for relativity report")
    parser.add_argument("--orb-pages", type=int, default=70, help="Target scale for orbital report")
    parser.add_argument("--calc-pages", type=int, default=35, help="Target scale for calculator report")
    args = parser.parse_args()

    engine = NablaMathProfessionalAllModules(Path(args.out))
    manifest = engine.build_all(args.rel_pages, args.orb_pages, args.calc_pages)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
