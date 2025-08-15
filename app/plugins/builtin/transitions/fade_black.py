# -*- coding: utf-8 -*-
"""
Transição fade to black
"""

from ...infra.plugins import effect
from ...domain.models.effects import Effect, FilterContext, FilterSnippet


@effect(
    name="fade_black",
    params={"duration": "float>0"},
    target="video",
    description="Transição para preto entre clipes",
)
class FadeBlackTransition(Effect):
    """Transição fade para preto"""

    def build_filter(self, ctx: FilterContext) -> FilterSnippet:
        duration = ctx.params.get("duration", 1.0)

        # Implementação simplificada - na prática seria mais complexa
        filter_expr = f"[{ctx.input_label}]fade=t=out:d={duration}[{ctx.output_label}]"
        return FilterSnippet(filter_expr)
