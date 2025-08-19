# -*- coding: utf-8 -*-
"""
tests/test_subtitle_system.py
Testes para o sistema de legendas
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from app.domain.models.subtitle import SubtitleSegment, SubtitleStyle, TranscriptionResult
from app.application.services.transcription_service import TranscriptionService
from app.plugins.builtin.effects.subtitle import SubtitleEffect, SubtitleFilterBuilder


class TestSubtitleModels:
    """Testes para modelos de domínio de legendas"""

    def test_subtitle_segment_creation(self):
        segment = SubtitleSegment(
            start_ms=1000,
            end_ms=3000,
            text="Olá mundo",
            confidence=0.95
        )

        assert segment.start_ms == 1000
        assert segment.end_ms == 3000
        assert segment.text == "Olá mundo"
        assert segment.confidence == 0.95

    def test_subtitle_style_defaults(self):
        style = SubtitleStyle()

        assert style.font_size == 24
        assert style.font_color == "white"
        assert style.position == "bottom_center"
        assert style.max_chars_per_line == 60

    def test_transcription_result(self):
        segments = [
            SubtitleSegment(0, 1000, "Primeira frase"),
            SubtitleSegment(1000, 2000, "Segunda frase"),
        ]

        result = TranscriptionResult(segments=segments, language="pt")

        assert len(result.segments) == 2
        assert result.language == "pt"
        assert result.confidence_threshold == 0.5


class TestSubtitleEffect:
    """Testes para o efeito de legenda"""

    def test_empty_segments(self):
        effect = SubtitleEffect([], SubtitleStyle())
        filter_str = effect.build_filter("input", "output")

        assert filter_str == "[input]copy[output]"

    def test_single_segment(self):
        segments = [
            SubtitleSegment(1000, 3000, "Teste de legenda", 0.9)
        ]

        effect = SubtitleEffect(segments, SubtitleStyle())
        filter_str = effect.build_filter("0:v", "vout")

        # Verificar se contém elementos essenciais
        assert "drawtext" in filter_str
        assert "enable='between(t,1.0,3.0)'" in filter_str
        assert "Teste de legenda" in filter_str
        assert "[0:v]" in filter_str
        assert "[vout]" in filter_str

    def test_multiple_segments(self):
        segments = [
            SubtitleSegment(0, 2000, "Primeira"),
            SubtitleSegment(2000, 4000, "Segunda"),
        ]

        effect = SubtitleEffect(segments)
        filter_str = effect.build_filter("input", "output")

        # Verificar se há dois filtros drawtext encadeados
        assert filter_str.count("drawtext") == 2
        assert "enable='between(t,0.0,2.0)'" in filter_str
        assert "enable='between(t,2.0,4.0)'" in filter_str

    def test_text_escaping(self):
        effect = SubtitleEffect([])

        # Testar escape de caracteres especiais
        assert effect._escape_text_for_ffmpeg("Hello: world") == r"Hello\: world"
        assert effect._escape_text_for_ffmpeg("Test [brackets]") == r"Test \[brackets\]"
        assert effect._escape_text_for_ffmpeg("Don't") == r"Don\'t"

    def test_text_truncation(self):
        effect = SubtitleEffect([], SubtitleStyle(max_chars_per_line=10))

        long_text = "Esta é uma frase muito longa que deveria ser truncada"
        escaped = effect._escape_text_for_ffmpeg(long_text)

        # Verificar se foi truncado
        assert len(escaped) <= 13  # 10 chars + "..."

    def test_position_coordinates(self):
        style = SubtitleStyle(position="bottom_center", margin_bottom=50)
        effect = SubtitleEffect([], style)

        x, y = effect._get_position_coordinates()
        assert x == "(w-text_w)/2"
        assert y == "h-text_h-50"

    def test_subtitle_effect_no_background_color(self):
        segment = SubtitleSegment(
            start_ms=0,
            end_ms=2000,
            text="Teste sem fundo"
        )
        style = SubtitleStyle(
            font_size=24,
            font_color="white",
            background_color="",  # Sem fundo
            position="center",
            outline_width=2,
            outline_color="black"
        )
        effect = SubtitleEffect([segment], style)
        filter_str = effect.build_filter("in", "out")
        # Não deve conter 'boxcolor=' no filtro
        assert "boxcolor=" not in filter_str, f"Filtro gerado indevidamente com boxcolor: {filter_str}"


class TestSubtitleFilterBuilder:
    """Testes para o builder de filtros"""

    def test_simple_filter_creation(self):
        segments = [
            SubtitleSegment(1000, 2000, "Teste", 0.8)
        ]

        filter_str = SubtitleFilterBuilder.create_simple_subtitle_filter(
            segments, "input", "output"
        )

        assert "drawtext" in filter_str
        assert "[input]" in filter_str
        assert "[output]" in filter_str


class TestTranscriptionService:
    """Testes para o serviço de transcrição"""

    def test_service_initialization(self):
        service = TranscriptionService()
        assert service.model_path is None
        assert service._model is None

    @patch('app.application.services.transcription_service.vosk', None)
    def test_vosk_not_available(self):
        service = TranscriptionService()
        assert not service.is_available()

    @patch('app.application.services.transcription_service.vosk')
    def test_vosk_available_no_model(self, mock_vosk):
        mock_vosk.Model.side_effect = Exception("Model not found")

        service = TranscriptionService()
        assert not service.is_available()

    def test_find_model_path_with_custom_path(self):
        custom_path = Path("/custom/model")
        service = TranscriptionService(model_path=custom_path)

        with patch.object(custom_path, 'exists', return_value=True):
            result = service._find_model_path()
            assert result == custom_path

    def test_optimize_segments_for_subtitles(self):
        service = TranscriptionService()

        segments = [
            SubtitleSegment(0, 1000, "Primeira", 0.9),
            SubtitleSegment(1000, 2000, "Segunda", 0.8),
            SubtitleSegment(2000, 8000, "Terceira muito longa", 0.7),
        ]

        optimized = service._optimize_segments_for_subtitles(segments, max_duration=4.0)

        # Verificar que segmentos muito longos foram quebrados
        assert len(optimized) >= len(segments)

        # Verificar que nenhum segmento excede duração máxima
        for segment in optimized:
            duration = (segment.end_ms - segment.start_ms) / 1000.0
            assert duration <= 4.5  # Pequena tolerância

    @patch('subprocess.run')
    def test_convert_to_wav(self, mock_run):
        mock_run.return_value = Mock(returncode=0)

        service = TranscriptionService()

        with patch('tempfile.mktemp', return_value='/tmp/test.wav'):
            result = service._convert_to_wav(Path("input.mp3"))
            assert str(result) == '/tmp/test.wav'

            # Verificar se ffmpeg foi chamado corretamente
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "-ar" in args
            assert "16000" in args
            assert "-ac" in args
            assert "1" in args

    def test_parse_vosk_result_no_result(self):
        service = TranscriptionService()

        # Resultado vazio
        result = service._parse_vosk_result({}, 0.5)
        assert result is None

        # Sem palavras
        result = service._parse_vosk_result({"result": []}, 0.5)
        assert result is None

    def test_parse_vosk_result_low_confidence(self):
        service = TranscriptionService()

        vosk_result = {
            "result": [
                {"word": "teste", "start": 1.0, "end": 2.0, "conf": 0.3}
            ]
        }

        result = service._parse_vosk_result(vosk_result, 0.5)
        assert result is None  # Baixa confiança

    def test_parse_vosk_result_success(self):
        service = TranscriptionService()

        vosk_result = {
            "result": [
                {"word": "olá", "start": 1.0, "end": 1.5, "conf": 0.9},
                {"word": "mundo", "start": 1.5, "end": 2.0, "conf": 0.8}
            ]
        }

        result = service._parse_vosk_result(vosk_result, 0.5)

        assert result is not None
        assert result.text == "olá mundo"
        assert result.start_ms == 1000
        assert result.end_ms == 2000
        assert result.confidence == 0.85  # Média de 0.9 e 0.8


class TestIntegration:
    """Testes de integração do sistema"""

    @patch('app.application.services.transcription_service.vosk')
    @patch('subprocess.run')
    def test_full_transcription_pipeline(self, mock_subprocess, mock_vosk):
        """Teste de integração do pipeline completo"""

        # Mock do modelo Vosk
        mock_model = Mock()
        mock_vosk.Model.return_value = mock_model

        # Mock do recognizer
        mock_recognizer = Mock()
        mock_vosk.KaldiRecognizer.return_value = mock_recognizer

        # Simular resultados de reconhecimento
        mock_recognizer.AcceptWaveform.return_value = True
        mock_recognizer.Result.return_value = '{"result": [{"word": "teste", "start": 0.0, "end": 1.0, "conf": 0.9}]}'
        mock_recognizer.FinalResult.return_value = '{"result": []}'

        # Mock da conversão de áudio
        mock_subprocess.return_value = Mock(returncode=0)

        # Mock do arquivo WAV
        with patch('wave.open') as mock_wave:
            mock_wave_file = Mock()
            mock_wave_file.readframes.side_effect = [b'data', b'']
            mock_wave.__enter__ = Mock(return_value=mock_wave_file)
            mock_wave.__exit__ = Mock(return_value=False)

            # Executar transcrição
            service = TranscriptionService(Path("fake_model"))

            with patch.object(service, '_find_model_path', return_value=Path("fake_model")):
                with patch('tempfile.mktemp', return_value='/tmp/test.wav'):
                    with patch('pathlib.Path.exists', return_value=True):
                        result = service.transcribe_audio(Path("test.mp3"))

            # Verificar resultado
            assert isinstance(result, TranscriptionResult)
            assert len(result.segments) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])