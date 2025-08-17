from .base import Transition


class NoneTransition(Transition):
    name = "none"

    def build_filter(self, duration: float, **kwargs) -> str:
        # Sem transição, retorna string vazia
        return ""
