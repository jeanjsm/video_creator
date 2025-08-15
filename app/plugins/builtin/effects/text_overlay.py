# -*- coding: utf-8 -*-
"""
Overlay de texto sobre vídeo
"""

from ...infra.plugins import effect
from ...domain.models.effects import Effect, FilterContext, FilterSnippet


@effect(
    name="text_overlay",
    params={
        "text": "str",
        "x": "int>=0",
        "y": "int>=0",
        "fontsize": "int>0",
        "color": "str",
    },
    target="video",
    description="Adiciona texto sobre o vídeo",
)
class TextOverlayEffect(Effect):
    """Efeito de overlay de texto"""

    def build_filter(self, ctx: FilterContext) -> FilterSnippet:
        text = ctx.params.get("text", "Sample Text")
        x = ctx.params.get("x", 10)
        y = ctx.params.get("y", 10)
        fontsize = ctx.params.get("fontsize", 24)
        color = ctx.params.get("color", "white")

        # Escapa o texto para FFmpeg
        escaped_text = text.replace(":", r"\:").replace("'", r"\'")

        filter_expr = f"[{ctx.input_label}]drawtext=text='{escaped_text}':x={x}:y={y}:fontsize={fontsize}:fontcolor={color}[{ctx.output_label}]"
        return FilterSnippet(filter_expr)
