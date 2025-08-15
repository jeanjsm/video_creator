# -*- coding: utf-8 -*-
"""
Testes de integração para renderização básica
"""

import pytest
import tempfile
from pathlib import Path

from app.rendering.graph_builder import GraphBuilder, FilterGraph
from app.rendering.cli_builder import CliBuilder
from app.domain.models.timeline import Timeline, RenderSettings
from fractions import Fraction


def test_graph_builder_empty_timeline():
    """Testa construção de filtergraph com timeline vazia"""
    timeline = Timeline(fps=Fraction(30, 1), resolution=(1920, 1080))
    builder = GraphBuilder()

    graph = builder.build(timeline)

    assert isinstance(graph, FilterGraph)
    # Timeline vazia não deve gerar filtros
    assert len(graph.filters) == 0


def test_cli_builder_basic():
    """Testa construção de comando FFmpeg básico"""
    graph = FilterGraph()
    settings = RenderSettings(
        container="mp4",
        vcodec="libx264",
        acodec="aac",
        crf=23,
        preset="medium",
        audio_bitrate="192k",
    )

    builder = CliBuilder()

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        output_path = Path(tmp.name)

    try:
        cmd = builder.make_command(graph, output_path, settings)

        assert len(cmd) > 0
        assert cmd[0].endswith(("ffmpeg", "ffmpeg.exe"))
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert str(output_path) in cmd
    finally:
        output_path.unlink(missing_ok=True)


def test_filter_graph_string_conversion():
    """Testa conversão de FilterGraph para string"""
    graph = FilterGraph()
    graph.add_filter("[0:v]scale=1920:1080[v1]")
    graph.add_filter("[v1]fade=t=in:d=1[vout]")

    filter_string = graph.to_string()

    assert "[0:v]scale=1920:1080[v1]" in filter_string
    assert "[v1]fade=t=in:d=1[vout]" in filter_string
    assert ";" in filter_string
