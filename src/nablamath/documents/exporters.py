"""Text is escaped per backend; generated prose cannot inject typesetting commands."""
from html import escape
import json
import re
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
    pieces = re.split(r'([^\s]{48,})', text)
    def escaped(value):
        return ''.join(replacements.get(char, char) for char in value)
    return ''.join(r'\allowbreak{}'.join(escaped(piece[i:i+24]) for i in range(0,len(piece),24))
                   if len(piece)>=48 and not any(c.isspace() for c in piece) else escaped(piece) for piece in pieces)


def to_html(document: Document) -> str:
    lines = ['<!doctype html><html lang="pt"><meta charset="utf-8">', f'<title>{escape(document.title)}</title>',
             f'<h1>{escape(document.title)}</h1>', f'<p>Sintetico: {document.synthetic}</p>']
    lines.append('<style>body{max-width:900px;margin:2rem auto;font-family:serif}pre{white-space:pre-wrap;overflow-wrap:anywhere}img{max-width:100%}</style>')
    for section in document.sections:
        lines.extend([f'<h2>{escape(section.heading)}</h2>', f'<pre>{escape(section.text)}</pre>',
                      f'<p>Evidencias: {escape(", ".join(section.evidence_ids + section.citations))}</p>'])
        lines.extend(f'<pre>{escape(render(eq.left))} = {escape(render(eq.right))}</pre>' for eq in section.equations)
        lines.extend(f'<figure><img src="{escape(fig.path)}" alt="{escape(fig.caption)}"><figcaption>{escape(fig.caption)}</figcaption></figure>' for fig in section.figures)
    lines += [f'<p>{escape(ref.text())}</p>' for ref in document.references]
    return '\n'.join(lines + [f'<p>{escape(document.limitations)}</p>', '</html>', ''])


def to_latex(document: Document) -> str:
    lines = [r'\documentclass{article}', r'\usepackage[T1]{fontenc}', r'\usepackage[utf8]{inputenc}', r'\usepackage{graphicx}', r'\usepackage{amsmath}', r'\usepackage[margin=2cm]{geometry}', r'\sloppy',
             r'\begin{document}', r'\section*{' + _tex(document.title) + '}',
             'Sintetico: ' + str(document.synthetic) + r'\par']
    for section in document.sections:
        lines.extend([r'\subsection*{' + _tex(section.heading) + '}', _tex(section.text) + r'\par',
                      'Evidencias: ' + _tex(', '.join(section.evidence_ids + section.citations)) + r'\par'])
        lines.extend(r'\[' + expression_latex(eq.left) + ' = ' + expression_latex(eq.right) + r'\]' for eq in section.equations)
        for fig in section.figures:
            lines.extend([r'\begin{center}\includegraphics[width=.8\linewidth]{' + fig.path + r'}\par', _tex(fig.caption) + r'\par', r'\end{center}'])
    lines += [_tex(ref.text()) + r'\par' for ref in document.references]
    return '\n'.join(lines + [_tex(document.limitations), r'\end{document}', ''])


def to_typst(document: Document) -> str:
    def literal(value: str) -> str:
        # Explicit break opportunities prevent provenance hashes from overflowing.
        wrapped = re.sub(r'[^\s]{48,}', lambda m: '\u200b'.join(m[0][i:i+24] for i in range(0,len(m[0]),24)), value)
        return json.dumps(wrapped, ensure_ascii=False)
    def text(value: str) -> str:
        return '#text(' + literal(value) + ')\n#parbreak()'
    def heading(value: str) -> str:
        return '#heading(level: 1, text(' + literal(value) + '))'
    lines = ['#set page(paper: "a4", margin: 2cm)', '#set text(size: 10pt)',
             '#set par(justify: true, leading: 0.6em)', '#set heading(numbering: "1.")',
             '#align(center, text(size: 18pt, weight: "bold", ' + literal(document.title) + '))',
             text('Sintetico: ' + str(document.synthetic))]
    for section in document.sections:
        lines.extend([heading(section.heading), text(section.text)])
        if section.evidence_ids or section.citations:
            lines.append(text('Evidencias: ' + ', '.join(section.evidence_ids + section.citations)))
        lines.extend('$ ' + _math(eq.left) + ' = ' + _math(eq.right) + ' $' for eq in section.equations)
        lines.extend('#figure(image(' + json.dumps(fig.path) + ', width: 90%), caption: text(' + literal(fig.caption) + '))' for fig in section.figures)
    if document.references:
        lines.append(heading('Referências'))
        lines += [text(ref.text()) for ref in document.references]
    return '\n\n'.join(lines + [heading('Limitações'), text(document.limitations), ''])
