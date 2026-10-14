"""Bibliographic metadata; references are supplied, never invented by exporters."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Citation:
    key: str
    title: str
    authors: tuple[str, ...]
    year: int
    url: str = ''
    doi: str = ''

    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', self.key):
            raise ValueError('Chave bibliográfica inválida')
        if not self.title.strip() or not self.authors or any(not a.strip() for a in self.authors):
            raise ValueError('Título e autores obrigatórios')
        if type(self.year) is not int or not 1 <= self.year <= 9999:
            raise ValueError('Ano inválido')
        if self.url and not self.url.startswith('https://'):
            raise ValueError('URL deve usar HTTPS')
        object.__setattr__(self, 'authors', tuple(self.authors))

    def text(self):
        return f'[{self.key}] {", ".join(self.authors)} ({self.year}). {self.title}. {self.doi or self.url}'
