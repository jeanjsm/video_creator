# -*- coding: utf-8 -*-
"""
Modelos de domínio para timeline, clips, efeitos e projetos
Baseado nas especificações do copilot-instructions.md
"""

from __future__ import annotations
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Literal, Mapping, Any


@dataclass(frozen=True)
class EffectRef:
    """Referência a um efeito aplicado a um clipe"""

    name: str  # ex: "fade", "xfade", "overlay", "logo"
    params: Mapping[str, str | int | float | bool]
    target: Literal["video", "audio", "both"] = "video"


@dataclass(frozen=True)
class Clip:
    """Representa um clipe de mídia na timeline"""

    id: str
    media_path: Path
    in_ms: int
    out_ms: int
    start_ms: int
    effects: list[EffectRef] = field(default_factory=list)


@dataclass(frozen=True)
class Track:
    """Representa uma track (faixa) de vídeo ou áudio"""

    id: str
    kind: Literal["video", "audio"]
    clips: list[Clip] = field(default_factory=list)


@dataclass(frozen=True)
class Timeline:
    """Representa a timeline completa do projeto"""

    fps: Fraction
    resolution: tuple[int, int]
    video: list[Track] = field(default_factory=list)
    audio: list[Track] = field(default_factory=list)


@dataclass(frozen=True)
class RenderSettings:
    """Configurações de renderização"""

    container: str  # "mp4"
    vcodec: str  # "libx264" | "h264_nvenc" | "hevc_nvenc" | "libx265"
    acodec: str  # "aac"
    crf: int  # 18-23
    preset: str  # "medium"
    audio_bitrate: str  # "192k"
    hwaccel: str | None = None  # "cuda"|"qsv"|"vaapi"|None


@dataclass
class Project:
    """Representa um projeto de vídeo"""

    audio_path: Path
    image_paths: list[Path]
    overlay_path: Path | None = None
    music_path: Path | None = None
    logo_path: Path | None = None
    timeline: Timeline | None = None
    render_settings: RenderSettings | None = None
