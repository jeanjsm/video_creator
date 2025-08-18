from app.domain.models.effects import EffectRef
from typing import Mapping


class LogoEffect:
    """Classe para encapsular o efeito de logo (imagem sobre o vídeo)."""

    def __init__(self, params: Mapping[str, str | int | float | bool]):
        self.path = params.get("path")
        self.position = params.get("position", "top_right")
        self.scale = params.get("scale", 0.15)
        self.opacity = params.get("opacity", 1.0)

    def build_filter(self, input_label: str, logo_label: str, output_label: str) -> str:
        # Mapeamento de posições
        position_map = {
            "top_left": "20:20",
            "top_right": "W-w-20:20",
            "bottom_left": "20:H-h-20",
            "bottom_right": "W-w-20:H-h-20",
            "center": "(W-w)/2:(H-h)/2",
        }
        pos = position_map.get(self.position, "W-w-20:20")
        scale_label = "logo_scaled"
        # Redimensionar logo
        scale_snippet = (
            f"[{logo_label}]scale=iw*{self.scale}:ih*{self.scale}[{scale_label}]"
        )
        # Opacidade
        if self.opacity != 1.0:
            alpha_label = "logo_alpha"
            alpha_snippet = f"[{scale_label}]format=rgba,colorchannelmixer=aa={self.opacity}[{alpha_label}]"
            overlay_input = f"[{alpha_label}]"
        else:
            alpha_snippet = ""
            overlay_input = f"[{scale_label}]"
        # Overlay
        overlay_snippet = f"[{input_label}]{overlay_input}overlay={pos}[{output_label}]"
        # Montar filtro completo
        filter_parts = [scale_snippet]
        if alpha_snippet:
            filter_parts.append(alpha_snippet)
        filter_parts.append(overlay_snippet)
        return ";".join(filter_parts)
