# -*- coding: utf-8 -*-
"""
Construção de comandos FFmpeg a partir do filtergraph
"""

from pathlib import Path
from typing import List
from .graph_builder import FilterGraph
from ..domain.models.timeline import RenderSettings


class CliBuilder:
    """Constrói comandos FFmpeg a partir do filtergraph"""

    def make_command(
        self, graph: FilterGraph, out_path: Path, settings: RenderSettings
    ) -> List[str]:
        """Gera o comando FFmpeg completo"""
        from ..infra.paths import ffmpeg_bin

        cmd = [ffmpeg_bin(), "-y"]

        # Adiciona inputs (seria passado pelo contexto)
        # Por simplicidade, assumindo um input padrão

        # Adiciona filtergraph se houver filtros
        if graph.filters:
            cmd.extend(["-filter_complex", graph.to_string()])

        # Configurações de codec
        cmd.extend(["-c:v", settings.vcodec])

        if settings.vcodec == "libx264":
            cmd.extend(["-preset", settings.preset, "-crf", str(settings.crf)])
        elif settings.vcodec == "h264_nvenc":
            cmd.extend(["-preset", "p5", "-rc", "constqp", "-qp", str(settings.crf)])

        # Codec de áudio
        cmd.extend(["-c:a", settings.acodec, "-b:a", settings.audio_bitrate])

        # Hardware acceleration se especificado
        if settings.hwaccel:
            cmd.extend(["-hwaccel", settings.hwaccel])

        # Formato de pixel e otimizações
        cmd.extend(["-pix_fmt", "yuv420p", "-movflags", "+faststart"])

        # Arquivo de saída
        cmd.append(str(out_path))

        return cmd
