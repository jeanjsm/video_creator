# -*- coding: utf-8 -*-
"""
Construção de filtergraph FFmpeg a partir da timeline
"""

from ..domain.models.timeline import Timeline, RenderSettings
from ..infra.logging import get_logger
from typing import List, Dict, Any
from pathlib import Path


class FilterGraph:
    """Representa um filtergraph FFmpeg"""

    def __init__(self):
        self.filters: List[str] = []
        self.inputs: List[Path] = []
        self.outputs: List[str] = []

    def add_input(self, input_path: Path):
        """Adiciona um input ao comando"""
        self.inputs.append(input_path)

    def add_filter(self, filter_expr: str):
        """Adiciona um filtro ao graph"""
        self.filters.append(filter_expr)

    def to_string(self) -> str:
        """Converte o filtergraph para string FFmpeg"""
        return ";".join(self.filters)


class GraphBuilder:
    """Constrói filtergraph a partir de timeline"""

    def __init__(self):
        self.logger = get_logger("GraphBuilder")

    def build(self, timeline: Timeline, settings: RenderSettings = None, overlays_chromakey: List[Dict[str, Any]] = None) -> FilterGraph:
        """Constrói o filtergraph para a timeline, incluindo overlays chromakey se fornecidos"""
        self.logger.info(
            "Construindo filtergraph para timeline com %d tracks de vídeo",
            len(timeline.video),
        )

        graph = FilterGraph()

        # Adicionar inputs de imagens primeiro
        for track in timeline.video:
            for clip in track.clips:
                graph.add_input(clip.media_path)

        # Adicionar inputs de overlays chromakey
        chroma_input_indices = []
        if overlays_chromakey:
            for overlay in overlays_chromakey:
                chroma_path = Path(overlay["path"])
                chroma_input_idx = len(graph.inputs)
                graph.add_input(chroma_path)
                chroma_input_indices.append((chroma_input_idx, overlay))

        # Adicionar inputs de áudio
        for track in timeline.audio:
            for clip in track.clips:
                graph.add_input(clip.media_path)

        # Construir filtros de vídeo
        self._build_video_filters(graph, timeline)

        # Aplicar overlays chromakey após [vout]
        if chroma_input_indices:
            last_label = "vout"
            for idx, overlay in chroma_input_indices:
                chroma_key = overlay.get("chromakey", "green")
                # Converter cor para formato hexadecimal se necessário
                color_map = {"green": "0x00FF00", "blue": "0x0000FF"}
                chroma_hex = color_map.get(chroma_key.lower(), chroma_key)
                chroma_label = f"ck{idx}"
                # chromakey filter
                graph.add_filter(f"[{idx}:v]chromakey={chroma_hex}:0.1:0.2[{chroma_label}]")
                # Posição
                pos = overlay.get("position", "center")
                pos_map = {
                    "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
                    "top_left": ("0", "0"),
                    "top_right": ("main_w-overlay_w", "0"),
                    "bottom_left": ("0", "main_h-overlay_h"),
                    "bottom_right": ("main_w-overlay_w", "main_h-overlay_h"),
                }
                x, y = pos_map.get(pos, ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"))
                # Tempo de início
                start = overlay.get("start", 0.0)
                # Overlay com enable para tempo
                out_label = f"vout{idx}"
                graph.add_filter(f"[{last_label}][{chroma_label}]overlay=x={x}:y={y}:enable='gte(t,{start})'[{out_label}]")
                last_label = out_label
            # Atualizar saída final
            graph.add_filter(f"[{last_label}]copy[vout_final]")
        else:
            graph.add_filter(f"[vout]copy[vout_final]")

        # Construir filtros de áudio se houver
        if timeline.audio:
            self._build_audio_filters(graph, timeline)

        self.logger.debug("Filtergraph construído: %s", graph.to_string())
        return graph

    def _build_video_filters(self, graph: FilterGraph, timeline: Timeline):
        """Constrói filtros de vídeo"""
        video_track = timeline.video[0] if timeline.video else None
        if not video_track:
            return

        # Para cada imagem, criar um segmento de vídeo
        segments = []

        for i, clip in enumerate(video_track.clips):
            segment_duration = (clip.out_ms - clip.in_ms) / 1000.0

            # Converter imagem para vídeo com duração específica
            vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2"

            input_label = f"{i}:v"
            output_label = f"seg{i}"

            # Filtro para converter imagem em segmento de vídeo
            segment_filter = f"[{input_label}]loop=loop=-1:size=1:start=0,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,trim=duration={segment_duration},setpts=PTS-STARTPTS[{output_label}]"

            graph.add_filter(segment_filter)
            segments.append(output_label)

        # Concatenar todos os segmentos
        if len(segments) > 1:
            concat_inputs = "".join(f"[{seg}]" for seg in segments)
            graph.add_filter(f"{concat_inputs}concat=n={len(segments)}:v=1:a=0[vout]")
        elif len(segments) == 1:
            graph.add_filter(f"[{segments[0]}]copy[vout]")

    def _build_audio_filters(self, graph: FilterGraph, timeline: Timeline):
        """Constrói filtros de áudio"""
        audio_clips = []
        audio_input_idx = len(timeline.video[0].clips) if timeline.video else 0

        for track in timeline.audio:
            for clip in track.clips:
                audio_clips.append((audio_input_idx, clip))
                audio_input_idx += 1

        if len(audio_clips) == 1:
            # Apenas um áudio
            idx, clip = audio_clips[0]
            graph.add_filter(f"[{idx}:a]volume=1.0[aout]")
        elif len(audio_clips) > 1:
            # Mixar múltiplos áudios
            narration_idx, narration_clip = audio_clips[0]
            bg_idx, bg_clip = audio_clips[1]

            # Aplicar volume aos áudios
            graph.add_filter(f"[{narration_idx}:a]volume=1.0[narr]")

            # Volume da música de fundo baseado nos efeitos do clip
            bg_volume = 0.2  # default
            for effect in bg_clip.effects:
                if effect.name == "volume":
                    bg_volume = effect.params.get("volume", 0.2)
                    break

            graph.add_filter(f"[{bg_idx}:a]volume={bg_volume}[bg]")

            # Mixar narração + música de fundo
            graph.add_filter(
                "[narr][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
