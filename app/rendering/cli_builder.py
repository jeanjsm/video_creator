# -*- coding: utf-8 -*-
"""
Construção de comandos FFmpeg a partir do filtergraph
"""

from pathlib import Path
from typing import List
from .graph_builder import FilterGraph
from ..domain.models.timeline import RenderSettings
from ..infra.logging import get_logger


class CliBuilder:
    """Constrói comandos FFmpeg a partir do filtergraph"""

    def __init__(self):
        self.logger = get_logger("CliBuilder")

    def make_command(
        self, graph: FilterGraph, out_path: Path, settings: RenderSettings
    ) -> List[str]:
        """Gera o comando FFmpeg completo"""
        from ..infra.paths import ffmpeg_bin

        self.logger.info("Construindo comando FFmpeg para %d inputs", len(graph.inputs))

        cmd = [ffmpeg_bin(), "-y"]

        # Hardware acceleration primeiro, se especificado
        if settings.hwaccel:
            cmd.extend(["-hwaccel", settings.hwaccel])

        # Adicionar todos os inputs
        for input_path in graph.inputs:
            if self._is_image(input_path):
                # Para imagens, usar loop para criar vídeo
                cmd.extend(["-loop", "1", "-i", str(input_path)])
            else:
                # Para vídeos/áudios normais
                cmd.extend(["-i", str(input_path)])

        # Adiciona filtergraph se houver filtros
        if graph.filters:
            cmd.extend(["-filter_complex", graph.to_string()])

            # Mapear outputs do filtergraph
            cmd.extend(["-map", "[vout]"])
            if any("aout" in f for f in graph.filters):
                cmd.extend(["-map", "[aout]"])
        else:
            # Sem filtergraph, mapear diretamente
            cmd.extend(["-map", "0:v"])
            if len(graph.inputs) > 1:
                cmd.extend(["-map", "1:a"])

        # Configurações de codec de vídeo
        cmd.extend(["-c:v", settings.vcodec])

        if settings.vcodec == "libx264":
            cmd.extend(["-preset", settings.preset, "-crf", str(settings.crf)])
        elif settings.vcodec == "h264_nvenc":
            cmd.extend(["-preset", "p5", "-rc", "constqp", "-qp", str(settings.crf)])

        # Codec de áudio
        cmd.extend(["-c:a", settings.acodec, "-b:a", settings.audio_bitrate])

        # Formato de pixel e otimizações
        cmd.extend(["-pix_fmt", "yuv420p", "-movflags", "+faststart"])

        # Arquivo de saída
        cmd.append(str(out_path))

        self.logger.debug("Comando FFmpeg: %s", " ".join(map(str, cmd)))
        return cmd

    def _is_image(self, file_path: Path) -> bool:
        """Verifica se o arquivo é uma imagem"""
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
        return file_path.suffix.lower() in image_extensions

    def make_image_to_video_command(
        self,
        image_path: Path,
        output_path: Path,
        duration: float,
        settings: RenderSettings,
    ) -> List[str]:
        """Cria comando para converter uma imagem em um clipe de vídeo"""
        from ..infra.paths import ffmpeg_bin

        self.logger.info(
            f"Construindo comando para converter {image_path.name} em vídeo de {duration}s"
        )

        cmd = [str(ffmpeg_bin()), "-y"]

        # Hardware acceleration se especificado
        if settings.hwaccel:
            cmd.extend(["-hwaccel", settings.hwaccel])

        # Input da imagem com loop
        cmd.extend(["-loop", "1", "-t", str(duration), "-i", str(image_path)])

        # Normalização da imagem (escala e pad para resolução padrão)
        filter_complex = (
            "[0:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2[vout]"
        )
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[vout]"])

        # Configurações de codec
        cmd.extend(["-c:v", settings.vcodec])
        if settings.vcodec == "libx264":
            cmd.extend(["-preset", "fast", "-crf", str(settings.crf)])
        elif settings.vcodec == "h264_nvenc":
            cmd.extend(["-preset", "p5", "-rc", "constqp", "-qp", str(settings.crf)])

        # Formato e framerate
        cmd.extend(["-pix_fmt", "yuv420p", "-r", "30"])

        # Arquivo de saída
        cmd.append(str(output_path))

        self.logger.debug("Comando de conversão: %s", " ".join(map(str, cmd)))
        return cmd

    def make_concat_command(
        self, video_files: List[Path], output_path: Path, settings: RenderSettings
    ) -> List[str]:
        """Cria comando para concatenar múltiplos vídeos"""
        from ..infra.paths import ffmpeg_bin

        self.logger.info(
            f"Construindo comando para concatenar {len(video_files)} vídeos"
        )

        cmd = [str(ffmpeg_bin()), "-y"]

        # Hardware acceleration se especificado
        if settings.hwaccel:
            cmd.extend(["-hwaccel", settings.hwaccel])

        # Adicionar todos os vídeos como inputs
        for video_file in video_files:
            cmd.extend(["-i", str(video_file)])

        # Filtro de concatenação
        filter_parts = []
        for i in range(len(video_files)):
            filter_parts.append(f"[{i}:v]")

        concat_filter = (
            "".join(filter_parts) + f"concat=n={len(video_files)}:v=1:a=0[vout]"
        )
        cmd.extend(["-filter_complex", concat_filter])
        cmd.extend(["-map", "[vout]"])

        # Configurações de codec (copy se possível, encode se necessário)
        cmd.extend(["-c:v", "libx264"])  # Reencoding para garantir compatibilidade
        cmd.extend(["-preset", "fast", "-crf", str(settings.crf)])
        cmd.extend(["-pix_fmt", "yuv420p"])

        # Arquivo de saída
        cmd.append(str(output_path))

        self.logger.debug("Comando de concatenação: %s", " ".join(map(str, cmd)))
        return cmd
