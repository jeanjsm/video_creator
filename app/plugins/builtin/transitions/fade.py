from .base import Transition


class FadeTransition(Transition):
    name = "fade"

    def build_filter(self, duration: float, **kwargs) -> str:
        # Exemplo: xfade=transition=fade:duration=1:offset=5
        offset = kwargs.get("offset", 0)
        return f"xfade=transition=fade:duration={duration}:offset={offset}"
