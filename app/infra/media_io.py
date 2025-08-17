# -*- coding: utf-8 -*-
"""
Serviços de mídia/IO para FFprobe e operações de arquivo
"""

import json
import subprocess
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from .logging import get_logger
from .paths import ffprobe_bin


class MediaIO:
    """Serviços de entrada/saída de mídia"""

    def __init__(self):
        self.logger = get_logger("MediaIO")

    def get_audio_duration(self, audio_path: Path) -> float:
        """Obtém duração do áudio em segundos"""
        if not audio_path or not audio_path.exists():
            return 0.0

        try:
            result = subprocess.run(
                [
                    ffprobe_bin(),
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            duration = float(data["format"]["duration"])
            self.logger.debug("Duração do áudio %s: %.2fs", audio_path, duration)
            return duration

        except Exception as e:
            self.logger.warning("Erro ao obter duração de %s: %s", audio_path, e)
            return 0.0

    def get_video_info(self, video_path: Path) -> dict:
        """Obtém informações do vídeo"""
        try:
            result = subprocess.run(
                [
                    ffprobe_bin(),
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,duration,fps",
                    "-of",
                    "json",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            stream = data["streams"][0]

            return {
                "width": int(stream.get("width", 1280)),
                "height": int(stream.get("height", 720)),
                "duration": float(stream.get("duration", 0)),
                "fps": eval(stream.get("avg_frame_rate", "30/1")),
            }

        except Exception as e:
            self.logger.warning("Erro ao obter info de %s: %s", video_path, e)
            return {"width": 1280, "height": 720, "duration": 0, "fps": 30}

    def get_image_size(self, image_path: Path) -> Tuple[int, int]:
        """Obtém dimensões da imagem"""
        try:
            result = subprocess.run(
                [
                    ffprobe_bin(),
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height",
                    "-of",
                    "json",
                    str(image_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            stream = data["streams"][0]
            width = int(stream["width"])
            height = int(stream["height"])

            self.logger.debug("Dimensões de %s: %dx%d", image_path, width, height)
            return width, height

        except Exception as e:
            self.logger.warning("Erro ao obter dimensões de %s: %s", image_path, e)
            return 1280, 720


# Funções legacy para compatibilidade
def get_media_info(file_path: Path) -> Dict[str, Any]:
    """Obtém informações de um arquivo de mídia usando ffprobe"""
    media_io = MediaIO()
    return media_io.get_video_info(file_path)


def get_video_duration(file_path: Path) -> float:
    """Obtém a duração de um arquivo de vídeo/áudio em segundos"""
    media_io = MediaIO()
    return media_io.get_audio_duration(file_path)


def get_video_resolution(file_path: Path) -> tuple[int, int]:
    """Obtém a resolução de um arquivo de vídeo"""
    media_io = MediaIO()
    return media_io.get_image_size(file_path)
