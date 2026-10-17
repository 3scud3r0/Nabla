"""Create real multipage scientific PDFs in Typst and LaTeX from one document.

Run: python examples/science/editorial_showcase.py NEW_OUTPUT_DIRECTORY
The comparison is synthetic and finite; errors are checked against exp(-t).
"""
import argparse
import json
import math
from pathlib import Path
import shutil

from nablamath.calc import CalculationSession
from nablamath.documents.document_model import Document,Section,Equation,Table
from nablamath.documents.citations import Citation
from nablamath.documents.pdf_builder import build_pdf
from nablamath.documents.exporters import to_typst,to_latex
from nablamath.expression import parse_expr


def demonstration_document():
    receipt=CalculationSession().execute('ode',model='exponential_decay',initial=[1.],duration=7,steps=70).to_data()
    rows=[]
    for t,state in receipt['result']['trajectory']:
        reference=math.exp(-t);error=abs(state[0]-reference)
        if error>4e-7:raise AssertionError('RK4 reference error exceeds the declared finite tolerance')
        rows.append((f'{t:.1f}',f'{state[0]:.8f}',f'{reference:.8f}',f'{error:.2e}'))
    table=Table('RK4 e referência analítica: todos os pontos registrados',
                ('Tempo','RK4','exp(-t)','Erro absoluto'),tuple(rows),(receipt['content_id'],))
    equations=(Equation(parse_expr('(x+y)**2'),parse_expr('x**2+2*x*y+y**2')),
               Equation(parse_expr('I'),parse_expr('1/3')))
    source=Citation('nabla','Nabla: snapshot de software consultado em 2026',('Nabla contributors',),2026,
                    url='https://github.com/3scud3r0/Nabla')
    document=Document('Métodos numéricos com evidência auditável',(
        Section('Objetivo e hipóteses','Este relatório apresenta uma demonstração sintética de integração numérica. '
                'O estado inicial é um e a taxa de decaimento é um, em unidades normalizadas. '
                'A comparação usa a solução analítica exp(-t), sem inferir validade experimental.',citations=('nabla',)),
        Section('Notação matemática','As equações abaixo ilustram a composição tipográfica de uma identidade polinomial '
                'e de um valor racional. O símbolo I representa a integral de x² de zero a um.',equations=equations),
        Section('Resultados e comparação independente','Os valores decimais da tabela são apresentados com precisão editorial; '
                'o recibo preserva os valores numéricos originais. Os cabeçalhos devem se repetir em cada página, '
                'sem cortar linhas ou esconder resultados.',evidence_ids=(receipt['content_id'],),tables=(table,)),
        Section('Discussão e limites','O erro é verificado apenas nos pontos desta trajetória e com a malha declarada. '
                'O modelo não representa observações físicas e a composição editorial não constitui revisão científica.'),
    ),limitations='Experimento sintético finito; sem certificação de precisão universal, revisão independente ou prova Lean.',
        references=(source,))
    return document,receipt


def run(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    document,receipt=demonstration_document()
    (destination/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (destination/'report.typ').write_text(to_typst(document),encoding='utf-8')
    (destination/'report.tex').write_text(to_latex(document),encoding='utf-8')
    outputs={}
    outputs['typst']=str(build_pdf(document,destination/'report-typst.pdf','typst'))
    if shutil.which('pdflatex'):
        outputs['latex']=str(build_pdf(document,destination/'report-latex.pdf','latex'))
    (destination/'summary.json').write_text(json.dumps({'document_id':document.content_id,'outputs':outputs},indent=2)+'\n')
    return outputs


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    print(json.dumps(run(parser.parse_args().destination),indent=2))
