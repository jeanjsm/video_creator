from app.domain.models.effects import EffectRef
from typing import Mapping


class OverlayEffect:
    """Classe para encapsular o efeito de overlay de vídeo."""

    def __init__(self, params: Mapping[str, str | int | float | bool]):
        self.path = params.get("path")
        self.opacity = params.get("opacity", 1.0)
        self.position = params.get("position", "center")
        self.scale = params.get("scale", 1.0)

    def build_filter(
        self, input_label: str, overlay_label: str, output_label: str
    ) -> str:
        # Exemplo: [input][overlay]overlay=x=...:y=...:format=auto[output]
        # Aqui, só retorna o snippet do filtergraph para FFmpeg
        # Posição e escala podem ser expandidos conforme necessário
        filter_snippet = f"[{input_label}][{overlay_label}]overlay=(W-w)/2:(H-h)/2:format=auto[{output_label}]"
        if self.opacity != 1.0:
            # Adiciona ajuste de opacidade se necessário
            filter_snippet = (
                f"[{overlay_label}]format=rgba,colorchannelmixer=aa={self.opacity}[overlay_alpha];"
                f"[{input_label}][overlay_alpha]overlay=(W-w)/2:(H-h)/2:format=auto[{output_label}]"
            )
        return filter_snippet
