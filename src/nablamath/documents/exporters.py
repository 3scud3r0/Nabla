"""Text is escaped per backend; generated prose cannot inject typesetting commands."""
from html import escape
import json
from .document_model import Document
from ..expression import Number, Symbol, render, to_latex as expression_latex


def _math(expr) -> str:
    if isinstance(expr, Number):
        return str(expr.value.numerator) if expr.value.denominator == 1 else f"({expr.value.numerator}/{expr.value.denominator})"
    if isinstance(expr, Symbol):
        return "upright(" + json.dumps(expr.name) + ")"
    op = "^" if expr.op == "**" else expr.op
    return f"({_math(expr.left)}) {op} ({_math(expr.right)})"



def _tex(text: str) -> str:
    replacements = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '&': r'\&', '%': r'\%',
                    '$': r'\$', '#': r'\#', '_': r'\_', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(replacements.get(char, char) for char in text)


def to_html(document: Document) -> str:
    lines = ['<!doctype html><html lang="pt"><meta charset="utf-8">', f'<title>{escape(document.title)}</title>',
             f'<h1>{escape(document.title)}</h1>', f'<p>Sintetico: {document.synthetic}</p>']
    lines.append('<style>body{max-width:900px;margin:2rem auto;font-family:serif}pre{white-space:pre-wrap;overflow-wrap:anywhere}img{max-width:100%}</style>')
    for section in document.sections:
        lines.extend([f'<h2>{escape(section.heading)}</h2>', f'<pre>{escape(section.text)}</pre>',
                      f'<p>Evidencias: {escape(", ".join(section.evidence_ids))}</p>'])
        lines.extend(f'<pre>{escape(render(eq.left))} = {escape(render(eq.right))}</pre>' for eq in section.equations)
        lines.extend(f'<figure><img src="{escape(fig.path)}" alt="{escape(fig.caption)}"><figcaption>{escape(fig.caption)}</figcaption></figure>' for fig in section.figures)
    return '\n'.join(lines + [f'<p>{escape(document.limitations)}</p>', '</html>', ''])


def to_latex(document: Document) -> str:
    lines = [r'\documentclass{article}', r'\usepackage[T1]{fontenc}', r'\usepackage[utf8]{inputenc}', r'\usepackage{graphicx}', r'\usepackage{amsmath}', r'\usepackage[margin=2cm]{geometry}', r'\sloppy',
             r'\begin{document}', r'\section*{' + _tex(document.title) + '}',
             'Sintetico: ' + str(document.synthetic) + r'\par']
    for section in document.sections:
        lines.extend([r'\subsection*{' + _tex(section.heading) + '}', _tex(section.text) + r'\par',
                      'Evidencias: ' + _tex(', '.join(section.evidence_ids)) + r'\par'])
        lines.extend(r'\[' + expression_latex(eq.left) + ' = ' + expression_latex(eq.right) + r'\]' for eq in section.equations)
        for fig in section.figures:
            lines.extend([r'\begin{center}\includegraphics[width=.8\linewidth]{' + fig.path + r'}\par', _tex(fig.caption) + r'\par', r'\end{center}'])
    return '\n'.join(lines + [_tex(document.limitations), r'\end{document}', ''])


def to_typst(document: Document) -> str:
    def text(value: str) -> str:
        return '#text(' + json.dumps(value, ensure_ascii=False) + ')\n#parbreak()'
    lines = [text(document.title), text('Sintetico: ' + str(document.synthetic))]
    for section in document.sections:
        lines.extend([text(section.heading), text(section.text), text('Evidencias: ' + ', '.join(section.evidence_ids))])
        lines.extend('$ ' + _math(eq.left) + ' = ' + _math(eq.right) + ' $' for eq in section.equations)
        lines.extend('#figure(image(' + json.dumps(fig.path) + ', width: 80%), caption: text(' + json.dumps(fig.caption, ensure_ascii=False) + '))' for fig in section.figures)
    return '\n'.join(lines + [text(document.limitations), ''])
