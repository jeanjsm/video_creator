# -*- coding: utf-8 -*-
"""
Transição de crossfade entre clipes
"""

from ...infra.plugins import effect
from ...domain.models.effects import Effect, FilterContext, FilterSnippet


@effect(
    name="crossfade",
    params={"duration": "float>0", "transition": "str"},
    target="video",
    description="Crossfade entre dois clipes de vídeo",
)
class CrossfadeTransition(Effect):
    """Transição de crossfade entre clipes"""

    def build_filter(self, ctx: FilterContext) -> FilterSnippet:
        duration = ctx.params.get("duration", 1.0)
        transition_type = ctx.params.get("transition", "fade")
        offset = ctx.params.get("offset", 0)

        # Assumindo que temos dois inputs: input1 e input2
        input1 = ctx.params.get("input1", ctx.input_label)
        input2 = ctx.params.get("input2", "v1")

        filter_expr = f"[{input1}][{input2}]xfade=transition={transition_type}:duration={duration}:offset={offset}[{ctx.output_label}]"
        return FilterSnippet(filter_expr)
