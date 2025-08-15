# -*- coding: utf-8 -*-
"""
Testes unitários para os modelos de domínio
"""

import pytest
from pathlib import Path
from fractions import Fraction

from app.domain.models.timeline import (
    Timeline,
    Track,
    Clip,
    EffectRef,
    Project,
    RenderSettings,
)


def test_clip_creation():
    """Testa criação de clipe"""
    clip = Clip(
        id="clip1", media_path=Path("test.mp4"), in_ms=0, out_ms=5000, start_ms=1000
    )

    assert clip.id == "clip1"
    assert clip.media_path == Path("test.mp4")
    assert clip.in_ms == 0
    assert clip.out_ms == 5000
    assert clip.start_ms == 1000
    assert len(clip.effects) == 0


def test_track_creation():
    """Testa criação de track"""
    track = Track(id="track1", kind="video")

    assert track.id == "track1"
    assert track.kind == "video"
    assert len(track.clips) == 0


def test_timeline_creation():
    """Testa criação de timeline"""
    timeline = Timeline(fps=Fraction(30, 1), resolution=(1920, 1080))

    assert timeline.fps == Fraction(30, 1)
    assert timeline.resolution == (1920, 1080)
    assert len(timeline.video) == 0
    assert len(timeline.audio) == 0


def test_effect_ref():
    """Testa referência a efeito"""
    effect = EffectRef(
        name="fade", params={"duration": 1.0, "type": "in"}, target="video"
    )

    assert effect.name == "fade"
    assert effect.params["duration"] == 1.0
    assert effect.target == "video"


def test_render_settings():
    """Testa configurações de renderização"""
    settings = RenderSettings(
        container="mp4",
        vcodec="libx264",
        acodec="aac",
        crf=23,
        preset="medium",
        audio_bitrate="192k",
    )

    assert settings.container == "mp4"
    assert settings.vcodec == "libx264"
    assert settings.hwaccel is None


def test_project_creation():
    """Testa criação de projeto"""
    project = Project(
        audio_path=Path("audio.mp3"), image_paths=[Path("img1.jpg"), Path("img2.jpg")]
    )

    assert project.audio_path == Path("audio.mp3")
    assert len(project.image_paths) == 2
    assert project.overlay_path is None
    assert project.timeline is None
