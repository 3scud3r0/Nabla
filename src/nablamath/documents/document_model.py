"""Scientific prose is explicitly synthetic and linked to evidence identifiers."""
from dataclasses import dataclass
import re
from ..expression import Expr


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
class Section:
    heading: str
    text: str
    evidence_ids: tuple[str, ...] = ()
    equations: tuple[Equation, ...] = ()
    figures: tuple[Figure, ...] = ()


@dataclass(frozen=True)
class Document:
    title: str
    sections: tuple[Section, ...]
    synthetic: bool = True
    limitations: str = "Exemplos sinteticos delimitados; sem prova Lean, revisao externa ou validacao experimental."

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.sections:
            raise ValueError("Documento requer titulo e secoes")
        if not self.limitations.strip():
            raise ValueError("Limitacoes devem ser declaradas")
