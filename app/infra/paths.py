# -*- coding: utf-8 -*-
"""
Paths utilities for FFmpeg binaries and project structure
"""

import os
from pathlib import Path


def ffmpeg_bin() -> str:
    """Resolve o caminho para o binário do FFmpeg"""
    base = Path(__file__).resolve().parents[3] / "_internal" / "ffmpeg" / "bin"
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    return str(base / exe_name)


def ffprobe_bin() -> str:
    """Resolve o caminho para o binário do FFprobe"""
    base = Path(__file__).resolve().parents[3] / "_internal" / "ffmpeg" / "bin"
    exe_name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    return str(base / exe_name)


def get_project_root() -> Path:
    """Retorna o diretório raiz do projeto"""
    return Path(__file__).resolve().parents[3]
