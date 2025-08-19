# -*- coding: utf-8 -*-
"""
app/domain/models/subtitle.py
Modelos de domínio para legendas e transcrição
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


@dataclass(frozen=True)
class SubtitleSegment:
    """Representa um segmento de legenda com timing"""

    start_ms: int
    end_ms: int
    text: str
    confidence: float = 1.0


@dataclass(frozen=True)
class SubtitleStyle:
    """Estilo de formatação das legendas"""

    font_size: int = 24
    font_color: str = "white"
    background_color: str = "black@0.5"  # Fundo semi-transparente
    position: str = "bottom_center"  # bottom_center, top_center, center
    margin_bottom: int = 50  # Pixels do fundo
    max_chars_per_line: int = 60  # Máximo de caracteres por linha
    max_words_per_line: int = 4  # Máximo de palavras por linha
    outline_width: int = 2
    outline_color: str = "black"
    # Novas opções de fonte
    font_file: str = None  # Caminho para arquivo de fonte (.ttf, .otf)
    font_family: str = None  # Nome da fonte do sistema (ex: "Arial", "Times New Roman")


@dataclass(frozen=True)
class TranscriptionResult:
    """Resultado da transcrição de áudio"""

    segments: List[SubtitleSegment]
    language: str = "pt"
    confidence_threshold: float = 0.5

    def save_as_srt(self, output_path: Path) -> None:
        """Salva os segmentos como arquivo SRT"""
        srt_content = []

        for i, segment in enumerate(self.segments, 1):
            # Converter milliseconds para formato SRT (HH:MM:SS,mmm)
            start_time = self._ms_to_srt_time(segment.start_ms)
            end_time = self._ms_to_srt_time(segment.end_ms)

            # Formato SRT:
            # 1
            # 00:00:01,000 --> 00:00:04,000
            # Texto da legenda
            #
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(segment.text)
            srt_content.append("")  # Linha em branco

        # Salvar arquivo SRT
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_content))

    def _ms_to_srt_time(self, ms: int) -> str:
        """Converte milliseconds para formato SRT (HH:MM:SS,mmm)"""
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        milliseconds = ms % 1000

        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
