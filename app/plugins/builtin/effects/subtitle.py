# -*- coding: utf-8 -*-
"""
app/plugins/builtin/effects/subtitle.py
Efeito para renderizar legendas no vídeo usando FFmpeg drawtext
"""

from typing import List, Mapping
from ....domain.models.subtitle import SubtitleSegment, SubtitleStyle


class SubtitleEffect:
    """Efeito para renderizar legendas queimadas no vídeo"""

    def __init__(self, segments: List[SubtitleSegment], style: SubtitleStyle = None):
        self.segments = segments
        self.style = style or SubtitleStyle()

    def build_filter(self, input_label: str, output_label: str) -> str:
        """
        Constrói filtro FFmpeg para renderizar todas as legendas

        Usa múltiplos filtros drawtext com enable para timing
        """
        if not self.segments:
            return f"[{input_label}]copy[{output_label}]"

        # Construir cadeia de filtros drawtext
        filter_parts = []
        current_input = input_label

        for i, segment in enumerate(self.segments):
            intermediate_label = f"sub{i}" if i < len(self.segments) - 1 else output_label

            # Calcular timing em segundos
            start_sec = segment.start_ms / 1000.0
            end_sec = segment.end_ms / 1000.0

            # Escapar texto para FFmpeg
            escaped_text = self._escape_text_for_ffmpeg(segment.text)

            # Posição baseada no estilo
            x_pos, y_pos = self._get_position_coordinates()

            # Configurar fonte
            font_params = self._get_font_parameters()

            # Construir filtro drawtext (corrigido)
            drawtext_parts = [
                f"text='{escaped_text}'",
                f"fontsize={self.style.font_size}",
                f"fontcolor={self.style.font_color}",
                f"x={x_pos}",
                f"y={y_pos}",
                f"borderw={self.style.outline_width}",
                f"bordercolor={self.style.outline_color}",
                "box=1",
                f"boxcolor={self.style.background_color}",
                "boxborderw=10"
            ]

            # Adicionar parâmetros de fonte apenas se não estiver vazio
            if font_params:
                drawtext_parts.append(font_params)

            # Adicionar enable
            drawtext_parts.append(f"enable='between(t,{start_sec},{end_sec})'")

            # Montar filtro completo
            drawtext_filter = f"[{current_input}]drawtext={':'.join(drawtext_parts)}[{intermediate_label}]"

            filter_parts.append(drawtext_filter)
            current_input = intermediate_label

        return ";".join(filter_parts)

    def _get_font_parameters(self) -> str:
        """Retorna parâmetros de fonte para FFmpeg"""
        font_params = []

        # Prioridade: arquivo de fonte > família de fonte > padrão
        if self.style.font_file:
            from pathlib import Path
            font_path = Path(self.style.font_file)
            if font_path.exists():
                # Escapar caminho para FFmpeg (importante no Windows)
                escaped_path = str(font_path).replace("\\", "/").replace(":", "\\:")
                font_params.append(f"fontfile='{escaped_path}'")
            else:
                # Se arquivo não existe, tentar como família
                if self.style.font_family:
                    font_params.append(f"font='{self.style.font_family}'")
                else:
                    # Usar fonte padrão do sistema
                    pass
        elif self.style.font_family:
            # Usar família de fonte do sistema
            font_params.append(f"font='{self.style.font_family}'")

        return ":".join(font_params) if font_params else ""

    def _escape_text_for_ffmpeg(self, text: str) -> str:
        """Escapa texto para uso no FFmpeg drawtext"""
        # Escapar caracteres especiais do FFmpeg
        text = text.replace("'", r"\'")
        text = text.replace(":", r"\:")
        text = text.replace("[", r"\[")
        text = text.replace("]", r"\]")
        text = text.replace(",", r"\,")
        text = text.replace(";", r"\;")

        # Agora que a segmentação é feita corretamente na transcrição,
        # não precisamos mais truncar com "..." aqui
        # O texto já vem com o tamanho correto do TranscriptionService
        return text

    def _get_position_coordinates(self) -> tuple[str, str]:
        """Retorna coordenadas de posição baseadas no estilo"""
        if self.style.position == "bottom_center":
            return "(w-text_w)/2", f"h-text_h-{self.style.margin_bottom}"
        elif self.style.position == "top_center":
            return "(w-text_w)/2", "text_h"
        elif self.style.position == "center":
            return "(w-text_w)/2", "(h-text_h)/2"
        elif self.style.position == "bottom_left":
            return "text_w", f"h-text_h-{self.style.margin_bottom}"
        elif self.style.position == "bottom_right":
            return "w-text_w-text_w", f"h-text_h-{self.style.margin_bottom}"
        else:
            # Default: bottom center
            return "(w-text_w)/2", f"h-text_h-{self.style.margin_bottom}"


class SubtitleFilterBuilder:
    """Builder para criar filtros de legenda mais complexos"""

    @staticmethod
    def create_simple_subtitle_filter(
            segments: List[SubtitleSegment],
            input_label: str = "0:v",
            output_label: str = "vout",
            style: SubtitleStyle = None
    ) -> str:
        """Cria filtro simples para legendas"""
        effect = SubtitleEffect(segments, style)
        return effect.build_filter(input_label, output_label)

    @staticmethod
    def create_animated_subtitle_filter(
            segments: List[SubtitleSegment],
            input_label: str = "0:v",
            output_label: str = "vout",
            fade_duration: float = 0.2
    ) -> str:
        """Cria filtro com animação de fade in/out (futuro)"""
        # Por enquanto, usar filtro simples
        # TODO: Implementar animações com fade
        return SubtitleFilterBuilder.create_simple_subtitle_filter(
            segments, input_label, output_label
        )