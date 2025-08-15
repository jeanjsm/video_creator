# -*- coding: utf-8 -*-
"""
Efeito de fade para vídeo
"""

from ...infra.plugins import effect
from ...domain.models.effects import Effect, FilterContext, FilterSnippet


@effect(
    name="fade",
    params={"start": "float>=0", "duration": "float>0", "inout": "'in'|'out'"},
    target="video",
    description="Aplica fade in ou fade out no vídeo",
)
class FadeEffect(Effect):
    """Efeito de fade para entrada ou saída"""

    def build_filter(self, ctx: FilterContext) -> FilterSnippet:
        start = ctx.params.get("start", 0)
        duration = ctx.params.get("duration", 1.0)
        inout = ctx.params.get("inout", "in")

        filter_expr = f"[{ctx.input_label}]fade=t={inout}:st={start}:d={duration}[{ctx.output_label}]"
        return FilterSnippet(filter_expr)
