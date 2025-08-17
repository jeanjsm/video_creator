from .fade import FadeTransition
from .smoothleft import SmoothLeftTransition
from .circleopen import CircleOpenTransition

from .zoomin import ZoomInTransition
from .none import NoneTransition

TRANSITIONS = {
    "fade": FadeTransition(),
    "smoothleft": SmoothLeftTransition(),
    "circleopen": CircleOpenTransition(),
    "none": NoneTransition(),
    "zoomin": ZoomInTransition(),
}


def get_transition(name: str):
    return TRANSITIONS.get(name, NoneTransition())
