"""Shared print typography; content is always supplied as escaped literals."""
import json
import re


def typst_literal(value):
    wrapped = re.sub(r'[^\s]{40,}', lambda match:'\u200b'.join(
        match[0][i:i+24] for i in range(0,len(match[0]),24)), str(value))
    return json.dumps(wrapped,ensure_ascii=False)


def typst_style(title, content_id, *, language='pt'):
    if language not in {'pt','en','es','fr','de'}:
        raise ValueError('Unsupported publication language')
    template = r'''
#let ink = rgb("172b3a")
#let accent = rgb("117879")
#let muted = rgb("526471")
#set document(title: TITLE)
#set page(paper: "a4", margin: (left: 22mm, right: 22mm, top: 23mm, bottom: 29mm),
  header: align(right, text(size: 7.5pt, fill: muted, "NABLA  /  SCIENTIFIC COMPUTING")),
  footer: context [
    #set text(font: "DejaVu Sans Mono", size: 6.5pt, fill: muted)
    #line(length: 100%, stroke: 0.4pt + rgb("c9d5db"))
    #v(3pt)
    #text("SHA-256: " + IDENTIFIER)
    #h(1fr) #counter(page).display()
  ])
#set text(font: ("Libertinus Serif", "New Computer Modern"), size: 10.5pt,
          lang: LANGUAGE, fill: ink, hyphenate: true)
#set par(justify: true, leading: 0.7em, spacing: 0.8em)
#set heading(numbering: "1.")
#show heading: it => block(above: 1.4em, below: 0.65em, sticky: true)[
  #set text(font: "DejaVu Sans", weight: "bold", fill: accent, hyphenate: false,
            size: if it.level == 1 { 12pt } else { 10.5pt })
  #it
]
#set math.equation(numbering: "(1)")
#show math.equation: set block(above: 0.9em, below: 0.9em)
#show figure.caption: set text(size: 8.5pt, fill: muted)
#show figure.where(kind: table): set block(breakable: true)
#set figure(gap: 7pt)
#set table(inset: (x: 6pt, y: 5pt), align: left,
           stroke: (x: none, y: 0.35pt + rgb("dbe3e7")),
           fill: (x,y) => if calc.odd(y) { rgb("f2f6f7") } else { none })
#let nabla-title(value, subtitle: none) = {
  block(above: 6mm, below: 7mm)[
    #text(font: "DejaVu Sans", size: 8pt, tracking: 1.2pt, fill: accent)[NABLA / RESEARCH]
    #v(9pt)
    #text(size: 24pt, weight: "bold", hyphenate: false, value)
    #if subtitle != none { v(8pt); text(size: 9pt, fill: muted, subtitle) }
    #v(12pt)
    #line(length: 22mm, stroke: 2pt + accent)
  ]
}
'''
    literals = {'TITLE':typst_literal(title),'IDENTIFIER':json.dumps(content_id),'LANGUAGE':json.dumps(language)}
    return re.sub(r'\b(TITLE|IDENTIFIER|LANGUAGE)\b',lambda match:literals[match[0]],template)
