"""Public server entry points backed by the existing local desktop application."""
from ..desktop.app import LocalResearch, make_server, main

__all__ = ['LocalResearch', 'make_server', 'main']
