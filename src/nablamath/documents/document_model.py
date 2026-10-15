"""Scientific prose is explicitly synthetic and linked to evidence identifiers."""
from dataclasses import dataclass
import re
from ..expression import Expr
from .citations import Citation


@dataclass(frozen=True)
class Equation:
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Figure:
    path: str
    caption: str

    def __post_init__(self):
        if not re.fullmatch(r"figures/[a-f0-9]{64}\.png", self.path):
            raise ValueError("Figura requer caminho relativo de artefato identificado por hash")


@dataclass(frozen=True)
class Table:
    caption: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'headers', tuple(self.headers))
        object.__setattr__(self, 'rows', tuple(tuple(row) for row in self.rows))
        object.__setattr__(self, 'evidence_ids', tuple(self.evidence_ids))
        if (not isinstance(self.caption, str) or not self.caption.strip()
                or not 1 <= len(self.headers) <= 12 or not 1 <= len(self.rows) <= 1000
                or any(len(row) != len(self.headers) for row in self.rows)
                or any(not isinstance(v, str) or len(v) > 4096 for v in (*self.headers, *(v for row in self.rows for v in row)))
                or any(not isinstance(v, str) or not v.strip() for v in self.evidence_ids)):
            raise ValueError('Tabela retangular limitada com legenda obrigatória')


@dataclass(frozen=True)
class Section:
    heading: str
    text: str
    evidence_ids: tuple[str, ...] = ()
    equations: tuple[Equation, ...] = ()
    figures: tuple[Figure, ...] = ()
    citations: tuple[str, ...] = ()
    tables: tuple[Table, ...] = ()

    def __post_init__(self):
        if not self.heading.strip() or not self.text.strip():
            raise ValueError("Seção requer título e conteúdo")
        for field in ("evidence_ids", "equations", "figures", "citations", "tables"):
            object.__setattr__(self, field, tuple(getattr(self, field)))


@dataclass(frozen=True)
class Document:
    title: str
    sections: tuple[Section, ...]
    synthetic: bool = True
    limitations: str = "Exemplos sinteticos delimitados; sem prova Lean, revisao externa ou validacao experimental."

    references: tuple[Citation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "references", tuple(self.references))
        keys = [ref.key for ref in self.references]
        if len(set(keys)) != len(keys) or any(key not in keys for section in self.sections for key in section.citations):
            raise ValueError("Referência duplicada ou não declarada")
        if type(self.synthetic) is not bool:
            raise ValueError("Origem sintética deve ser explícita")
        if not self.title.strip() or not self.sections:
            raise ValueError("Documento requer titulo e secoes")
        if not self.limitations.strip():
            raise ValueError("Limitacoes devem ser declaradas")


    def to_data(self):
        from dataclasses import asdict
        from .equation_blocks import equation_data
        return {'schema_version': 2 if any(s.tables for s in self.sections) else 1, 'title': self.title, 'synthetic': self.synthetic,
                'limitations': self.limitations, 'references': [asdict(r) for r in self.references],
                'sections': [{'heading': s.heading, 'text': s.text, 'evidence_ids': list(s.evidence_ids),
                              'equations': [equation_data(e) for e in s.equations],
                              'figures': [asdict(f) for f in s.figures], 'citations': list(s.citations),
                              **({'tables': [asdict(t) for t in s.tables]} if s.tables else {})}
                             for s in self.sections]}

    @property
    def content_id(self):
        from ..core.semantic_ir import fingerprint
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls, data):
        from .equation_blocks import equation_from_data
        if data['schema_version'] not in (1, 2):
            raise ValueError('Versão de documento desconhecida')
        return cls(data['title'], tuple(Section(s['heading'], s['text'], tuple(s['evidence_ids']),
                   tuple(equation_from_data(e) for e in s['equations']),
                   tuple(Figure(**f) for f in s['figures']), tuple(s['citations']),
                   tuple(Table(**t) for t in s.get('tables', ()))) for s in data['sections']),
                   data['synthetic'], data['limitations'], tuple(Citation(**r) for r in data['references']))
