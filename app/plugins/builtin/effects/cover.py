from app.domain.models.effects import EffectRef
from typing import Mapping


class CoverEffect:
    """Classe para encapsular o efeito de capa (imagem sobre o vídeo)."""

    def __init__(self, params: Mapping[str, str | int | float | bool]):
        self.path = params.get("path")
        self.position = params.get("position", "center")
        self.size = params.get("size", 1.0)
        self.opacity = params.get("opacity", 1.0)

    def build_filter(
        self, input_label: str, cover_label: str, output_label: str
    ) -> str:
        position_map = {
            "center": "(W-w)/2:(H-h)/2",
            "top_left": "2:2",
            "top_right": "W-w-2:2",
            "bottom_left": "2:H-h-2",
            "bottom_right": "W-w-2:H-h-2",
        }
        pos = position_map.get(self.position, position_map["center"])
        # Redimensionar capa
        if self.size != 1.0:
            scale_label = "cover_scaled"
            scale_snippet = (
                f"[{cover_label}]scale=iw*{self.size}:ih*{self.size}[{scale_label}]"
            )
            cover_input = f"[{scale_label}]"
        else:
            scale_snippet = ""
            cover_input = f"[{cover_label}]"
        # Opacidade
        if self.opacity != 1.0:
            alpha_label = "cover_alpha"
            alpha_snippet = f"{cover_input}format=rgba,colorchannelmixer=aa={self.opacity}[{alpha_label}]"
            overlay_input = f"[{alpha_label}]"
        else:
            alpha_snippet = ""
            overlay_input = cover_input
        # Overlay
        overlay_snippet = f"[{input_label}]{overlay_input}overlay={pos}[{output_label}]"
        # Montar filtro completo
        filter_parts = []
        if scale_snippet:
            filter_parts.append(scale_snippet)
        if alpha_snippet:
            filter_parts.append(alpha_snippet)
        filter_parts.append(overlay_snippet)
        return ";".join(filter_parts)
