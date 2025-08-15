# -*- coding: utf-8 -*-
"""
FFmpeg utilities and media analysis
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any
from .paths import ffprobe_bin


def get_media_info(file_path: Path) -> Dict[str, Any]:
    """Obtém informações de um arquivo de mídia usando ffprobe"""
    ffprobe = ffprobe_bin()
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except Exception:
        return {}


def get_video_duration(file_path: Path) -> float:
    """Obtém a duração de um arquivo de vídeo/áudio em segundos"""
    info = get_media_info(file_path)
    try:
        return float(info["format"]["duration"])
    except (KeyError, ValueError):
        return 0.0


def get_video_resolution(file_path: Path) -> tuple[int, int]:
    """Obtém a resolução de um arquivo de vídeo"""
    info = get_media_info(file_path)
    try:
        for stream in info["streams"]:
            if stream["codec_type"] == "video":
                return int(stream["width"]), int(stream["height"])
    except (KeyError, ValueError):
        pass
    return 1280, 720  # resolução padrão
