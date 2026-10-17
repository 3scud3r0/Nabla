"""Text is escaped per backend; generated prose cannot inject typesetting commands."""
from html import escape
import json
import re
from .document_model import Document
from ..expression import Number, Symbol, render, to_latex as expression_latex
from .typesetting import typst_style,typst_literal


def _math(expr, parent=0) -> str:
    if isinstance(expr, Number):
        return str(expr.value.numerator) if expr.value.denominator == 1 else f"frac({expr.value.numerator},{expr.value.denominator})"
    if isinstance(expr, Symbol):
        return expr.name if re.fullmatch('[A-Za-z]',expr.name) else "upright(" + json.dumps(expr.name) + ")"
    if expr.op == '/':return f"frac({_math(expr.left)},{_math(expr.right)})"
    if expr.op == '**':
        base=_math(expr.left)
        if not isinstance(expr.left,(Number,Symbol)) or isinstance(expr.left,Number) and expr.left.value<0:base='('+base+')'
        return base+'^('+_math(expr.right)+')'
    precedence=10 if expr.op in ('+','-') else 20
    operator=' ' if expr.op=='*' else ' '+expr.op+' '
    result=_math(expr.left,precedence)+operator+_math(expr.right,precedence+int(expr.op=='-'))
    return '('+result+')' if precedence<parent else result


def _latex_math(expr,parent=0):
    if isinstance(expr,(Number,Symbol)):return expression_latex(expr)
    if expr.op=='/':return r'\frac{'+_latex_math(expr.left)+'}{'+_latex_math(expr.right)+'}'
    if expr.op=='**':
        base=_latex_math(expr.left)
        if not isinstance(expr.left,(Number,Symbol)) or isinstance(expr.left,Number) and expr.left.value<0:
            base=r'\left('+base+r'\right)'
        return base+'^{'+_latex_math(expr.right)+'}'
    precedence=10 if expr.op in ('+','-') else 20
    operator=r'\,' if expr.op=='*' else ' '+expr.op+' '
    result=_latex_math(expr.left,precedence)+operator+_latex_math(expr.right,precedence+int(expr.op=='-'))
    return r'\left('+result+r'\right)' if precedence<parent else result



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
        for table in section.tables:
            lines.append('<table><caption>'+escape(table.caption)+'</caption><thead><tr>'+''.join('<th scope="col">'+escape(v)+'</th>' for v in table.headers)+'</tr></thead><tbody>')
            lines.extend('<tr>'+''.join('<td>'+escape(v)+'</td>' for v in row)+'</tr>' for row in table.rows)
            lines.append('</tbody></table>')
            lines.append('<p>Evidencias: '+escape(', '.join(table.evidence_ids))+'</p>')
    lines += [f'<p>{escape(ref.text())}</p>' for ref in document.references]
    return '\n'.join(lines + [f'<p>{escape(document.limitations)}</p>', '</html>', ''])


def to_latex(document: Document) -> str:
    lines = [r'\documentclass[10pt,a4paper]{article}', r'\usepackage[T1]{fontenc}', r'\usepackage[utf8]{inputenc}',
             r'\usepackage{graphicx,amsmath,array,longtable,booktabs,microtype,fancyhdr,xcolor}',
             r'\IfFileExists{lmodern.sty}{\usepackage{lmodern}}{}',r'\microtypesetup{expansion=false}',
             r'\usepackage[left=22mm,right=22mm,top=25mm,bottom=27mm]{geometry}',
             r'\definecolor{nablaAccent}{HTML}{117879}', r'\definecolor{nablaMuted}{HTML}{526471}',
             r'\setlength{\parindent}{0pt}', r'\setlength{\parskip}{.65em}', r'\linespread{1.08}',
             r'\setlength{\headheight}{14pt}', r'\pagestyle{fancy}\fancyhf{}',
             r'\fancyhead[R]{\small\sffamily\textcolor{nablaMuted}{NABLA / SCIENTIFIC COMPUTING}}',
             r'\fancyfoot[L]{\fontsize{6.3}{7.5}\selectfont\ttfamily SHA-256: '+document.content_id+'}',
             r'\fancyfoot[R]{\small\thepage}', r'\renewcommand{\headrulewidth}{0pt}',
             r'\renewcommand{\footrulewidth}{.4pt}',r'\emergencystretch=2em',
             r'\begin{document}', r'{\small\sffamily\textcolor{nablaAccent}{NABLA / RESEARCH}}\par',
             r'{\LARGE\bfseries ' + _tex(document.title) + r'}\par\medskip',
             'Sintetico: ' + str(document.synthetic) + r'\par']
    for section in document.sections:
        lines.extend([r'\section{\textcolor{nablaAccent}{' + _tex(section.heading) + '}}', _tex(section.text) + r'\par'])
        if section.evidence_ids or section.citations:
            lines.append('Evidencias: ' + _tex(', '.join(section.evidence_ids + section.citations)) + r'\par')
        lines.extend(r'\begin{equation}' + _latex_math(eq.left) + ' = ' + _latex_math(eq.right) + r'\end{equation}' for eq in section.equations)
        for fig in section.figures:
            lines.extend([r'\begin{figure}[htbp]\centering\includegraphics[width=\linewidth,height=95mm,keepaspectratio]{' + fig.path + '}',
                          r'\caption{'+_tex(fig.caption)+'}',r'\end{figure}'])
        for table in section.tables:
            column = r'>{\raggedright\arraybackslash}p{\dimexpr\linewidth/'+str(len(table.headers))+r'-2\tabcolsep\relax}'
            lines.extend([r'\begin{longtable}{'+column*len(table.headers)+'}',r'\caption{'+_tex(table.caption)+r'}\\',r'\toprule'])
            header = ' & '.join(r'\textbf{'+_tex(v)+'}' for v in table.headers)+r'\\ \midrule'
            lines.extend([header,r'\endfirsthead',r'\toprule',header,r'\endhead',r'\bottomrule\endfoot'])
            lines.extend(' & '.join(_tex(v) for v in row)+r'\\' for row in table.rows)
            lines.extend([r'\end{longtable}', r'\par Evidencias: '+_tex(', '.join(table.evidence_ids))])
    lines += [_tex(ref.text()) + r'\par' for ref in document.references]
    return '\n'.join(lines + [_tex(document.limitations), r'\end{document}', ''])


def to_typst(document: Document) -> str:
    def literal(value: str) -> str:
        return typst_literal(value)
    def text(value: str) -> str:
        return '#text(' + literal(value) + ')\n#parbreak()'
    def heading(value: str) -> str:
        return '#heading(level: 1, text(' + literal(value) + '))'
    lines = [typst_style(document.title,document.content_id),
             '#nabla-title('+literal(document.title)+', subtitle: '+literal('Sintetico: ' + str(document.synthetic))+')']
    for section in document.sections:
        lines.extend([heading(section.heading), text(section.text)])
        if section.evidence_ids or section.citations:
            lines.append(text('Evidencias: ' + ', '.join(section.evidence_ids + section.citations)))
        lines.extend('$ ' + _math(eq.left) + ' = ' + _math(eq.right) + ' $' for eq in section.equations)
        lines.extend('#figure(align(center, image(' + json.dumps(fig.path) + ', width: 100%, height: 95mm, fit: "contain")), caption: text(' + literal(fig.caption) + '))' for fig in section.figures)
        for table in section.tables:
            cells = [v for row in table.rows for v in row]
            lines.append('#figure(table(columns: '+str(len(table.headers))+', '+
                         'table.header(repeat: true, '+', '.join('strong(text('+literal(v)+'))' for v in table.headers)+'), '+
                         ', '.join('text('+literal(v)+')' for v in cells)+
                         '), caption: text('+literal(table.caption)+'), kind: table)')
            if table.evidence_ids:
                lines.append(text('Evidencias: '+', '.join(table.evidence_ids)))
    if document.references:
        lines.append(heading('Referências'))
        lines += [text(ref.text()) for ref in document.references]
    return '\n\n'.join(lines + [heading('Limitações'), text(document.limitations), ''])
