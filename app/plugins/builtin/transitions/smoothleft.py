from .base import Transition


class SmoothLeftTransition(Transition):
    name = "smoothleft"

    def build_filter(self, duration: float, **kwargs) -> str:
        offset = kwargs.get("offset", 0)
        return f"xfade=transition=smoothleft:duration={duration}:offset={offset}"
