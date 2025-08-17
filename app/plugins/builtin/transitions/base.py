from abc import ABC, abstractmethod
from typing import Any


class Transition(ABC):
    """Classe base para transições de vídeo."""

    name: str

    @abstractmethod
    def build_filter(self, duration: float, **kwargs) -> str:
        """Retorna o snippet do filtro FFmpeg para a transição."""
        pass
