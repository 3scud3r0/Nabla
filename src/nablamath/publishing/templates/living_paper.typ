// Results are typed data, never evaluated as Typst source.
#let scalar(item) = {
  if item.kind == "exact" {
    if item.denominator == "1" { math.upright(item.numerator) }
    else { math.frac(math.upright(item.numerator), math.upright(item.denominator)) }
  } else if item.kind == "approximate" {
    [#math.approx #math.upright(item.text)]
  } else { text(item.text) }
}
#let result-value(item) = {
  if item.kind == "vector" { math.vec(..item.items.map(scalar)) }
  else if item.kind == "matrix" { math.mat(..item.rows.map(row => row.map(scalar))) }
  else { scalar(item) }
}
#nabla-title(nabla.title, subtitle: "Reproducible computational report")
#if nabla.authors.len() > 0 { text(size: 10pt, fill: muted, nabla.authors.join(" · ")); parbreak() }
#if nabla.abstract != "" {
  block(fill: rgb("f2f6f7"), inset: 12pt, radius: 3pt, width: 100%)[
    #text(font: "DejaVu Sans", weight: "bold", size: 8pt, fill: accent)[ABSTRACT]
    #v(5pt)
    #text(size: 9.5pt, nabla.abstract)
  ]
  v(7pt)
}
#let results-section() = [
  = Computed results
  #for item in nabla.results {
    block(above: 6pt, below: 8pt, breakable: false)[
      #text(font: "DejaVu Sans", size: 8pt, fill: muted, item.name)
      #v(3pt)
      #set text(size: 11pt)
      #result-value(item.value)
    ]
  }
  #text(size: 8pt, fill: muted)[Decimal values marked ≈ use ten significant digits. Complete values remain in the experiment bundle.]

]
#let figures-section(compact: false) = [
  = Figures
  #for item in nabla.images {
    figure(align(center, image(item.path, width: 100%, height: if compact { 58mm } else { 85mm }, fit: "contain")), caption: item.caption)
  }
]
// Compact summaries use both columns. Long reports use a flowing full-width body.
#if nabla.results.len() <= 8 and nabla.images.len() == 1 {
  grid(columns: (1fr, 1fr), gutter: 8mm, results-section(), figures-section(compact: true))
} else {
  results-section()
  if nabla.images.len() > 0 { figures-section() }
}
= Provenance and scope
#text(size: 8.5pt)[The footer identifies the experiment and the laboratory signature. The manifest binds source, figures and PDF to their SHA-256 digests.]

#text(size: 8.5pt)[Computational evidence does not establish experimental validity, novelty, independent review or a formal proof of the paper's prose.]
