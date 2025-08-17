from .base import Transition


class CircleOpenTransition(Transition):
    name = "circleopen"

    def build_filter(self, duration: float, **kwargs) -> str:
        offset = kwargs.get("offset", 0)
        return f"xfade=transition=circleopen:duration={duration}:offset={offset}"
