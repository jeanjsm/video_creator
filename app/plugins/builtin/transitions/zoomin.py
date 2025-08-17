from .base import Transition


class ZoomInTransition(Transition):
    name = "zoomin"

    def build_filter(self, duration: float, **kwargs) -> str:
        offset = kwargs.get("offset", 0)
        # O filtro xfade do ffmpeg suporta 'zoomin' como tipo de transição
        return f"xfade=transition=zoomin:duration={duration}:offset={offset}"
