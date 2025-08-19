# -*- coding: utf-8 -*-
"""
app/application/services/transcription_service.py
Serviço de transcrição de áudio usando Vosk
"""

import json
import wave
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

try:
    import vosk
except ImportError:
    vosk = None

from ...domain.models.subtitle import SubtitleSegment, TranscriptionResult
from ...infra.logging import get_logger
from ...infra.paths import ffmpeg_bin


class TranscriptionService:
    """Serviço para transcrever áudio em legendas usando Vosk"""

    def __init__(self, model_path: Optional[Path] = None):
        self.logger = get_logger("TranscriptionService")
        self.model_path = model_path
        self._model = None

        if vosk is None:
            self.logger.warning("Vosk não instalado. Legendas não estarão disponíveis.")

    def is_available(self) -> bool:
        """Verifica se o serviço está disponível"""
        return vosk is not None and self._get_model() is not None

    def transcribe_audio(
            self,
            audio_path: Path,
            confidence_threshold: float = 0.5,
            max_segment_duration: float = 4.0,
            max_chars_per_line: int = 60,
            max_words_per_line: int = 4
    ) -> TranscriptionResult:
        """
        Transcreve áudio para legendas

        Args:
            audio_path: Caminho para o arquivo de áudio
            confidence_threshold: Limiar mínimo de confiança
            max_segment_duration: Duração máxima de cada segmento em segundos
            max_chars_per_line: Número máximo de caracteres por linha
        """
        if not self.is_available():
            raise RuntimeError("Vosk não está disponível ou modelo não encontrado")

        self.logger.info(f"Iniciando transcrição de {audio_path}")

        # Converter áudio para formato WAV mono 16kHz (requerido pelo Vosk)
        wav_path = self._convert_to_wav(audio_path)

        try:
            segments = self._process_audio_with_vosk(wav_path, confidence_threshold)

            # Otimizar segmentos para legendas (máximo 1 linha)
            optimized_segments = self._optimize_segments_for_subtitles(
                segments, max_segment_duration, max_chars_per_line, max_words_per_line
            )

            self.logger.info(f"Transcrição concluída: {len(optimized_segments)} segmentos")

            return TranscriptionResult(
                segments=optimized_segments,
                language="pt",
                confidence_threshold=confidence_threshold
            )

        finally:
            # Cleanup do arquivo temporário
            if wav_path.exists():
                wav_path.unlink()

    def _get_model(self) -> Optional[vosk.Model]:
        """Obtém o modelo Vosk (lazy loading)"""
        if self._model is not None:
            return self._model

        if vosk is None:
            return None

        # Tentar encontrar modelo
        model_path = self._find_model_path()
        if not model_path:
            self.logger.error("Modelo Vosk não encontrado")
            return None

        try:
            self._model = vosk.Model(str(model_path))
            self.logger.info(f"Modelo Vosk carregado: {model_path}")
            return self._model
        except Exception as e:
            self.logger.error(f"Erro ao carregar modelo Vosk: {e}")
            return None

    def _find_model_path(self) -> Optional[Path]:
        """Encontra o caminho do modelo Vosk"""
        if self.model_path and self.model_path.exists():
            return self.model_path

        # Locais padrão para buscar o modelo
        possible_paths = [
            Path("vosk-model"),
            Path("_internal/vosk-model"),
            Path("models/vosk-model"),
            Path.home() / ".vosk" / "models",
        ]

        for path in possible_paths:
            if path.exists() and (path / "am").exists():
                return path

        self.logger.warning("Modelo Vosk não encontrado nos caminhos padrão")
        return None

    def _convert_to_wav(self, audio_path: Path) -> Path:
        """Converte áudio para WAV mono 16kHz"""
        temp_wav = Path(tempfile.mktemp(suffix=".wav"))

        cmd = [
            str(ffmpeg_bin()),
            "-i", str(audio_path),
            "-ar", "16000",  # Sample rate 16kHz
            "-ac", "1",  # Mono
            "-c:a", "pcm_s16le",  # 16-bit PCM
            "-y",
            str(temp_wav)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=True
            )
            self.logger.debug("Áudio convertido para WAV")
            return temp_wav

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Erro na conversão de áudio: {e.stderr}")
            raise RuntimeError(f"Falha na conversão de áudio: {e.stderr}")

    def _process_audio_with_vosk(
            self,
            wav_path: Path,
            confidence_threshold: float
    ) -> List[SubtitleSegment]:
        """Processa áudio com Vosk e retorna segmentos"""
        model = self._get_model()
        if not model:
            raise RuntimeError("Modelo Vosk não disponível")

        # Configurar recognizer
        rec = vosk.KaldiRecognizer(model, 16000)
        rec.SetWords(True)  # Habilitar timestamps de palavras

        segments = []

        with wave.open(str(wav_path), 'rb') as wf:
            while True:
                data = wf.readframes(4000)  # Chunks de ~0.25s
                if len(data) == 0:
                    break

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    segment = self._parse_vosk_result(result, confidence_threshold)
                    if segment:
                        segments.append(segment)

            # Processar último chunk
            final_result = json.loads(rec.FinalResult())
            final_segment = self._parse_vosk_result(final_result, confidence_threshold)
            if final_segment:
                segments.append(final_segment)

        return segments

    def _parse_vosk_result(
            self,
            result: dict,
            confidence_threshold: float
    ) -> Optional[SubtitleSegment]:
        """Converte resultado do Vosk em SubtitleSegment"""
        if not result.get("result"):
            return None

        words = result["result"]
        if not words:
            return None

        # Calcular confiança média
        confidences = [word.get("conf", 0) for word in words]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        if avg_confidence < confidence_threshold:
            return None

        # Extrair texto e timing
        text = " ".join(word["word"] for word in words)
        start_time = words[0]["start"]
        end_time = words[-1]["end"]

        return SubtitleSegment(
            start_ms=int(start_time * 1000),
            end_ms=int(end_time * 1000),
            text=text.strip(),
            confidence=avg_confidence
        )

    def _optimize_segments_for_subtitles(
            self,
            segments: List[SubtitleSegment],
            max_duration: float,
            max_chars_per_line: int,
            max_words_per_line: int
    ) -> List[SubtitleSegment]:
        """
        Otimiza segmentos para exibição como legendas com limite de palavras por linha
        """
        if not segments:
            return []

        self.logger.info(f"Otimizando {len(segments)} segmentos para legendas (max_words: {max_words_per_line})")

        # Concatenar todos os segmentos em uma lista de palavras com timing individual
        all_words = []
        for segment in segments:
            words = segment.text.split()
            if not words:
                continue

            # Calcular timing por palavra dentro do segmento
            segment_duration_ms = segment.end_ms - segment.start_ms
            word_duration_ms = segment_duration_ms / len(words) if len(words) > 0 else 0

            for i, word in enumerate(words):
                word_start_ms = segment.start_ms + int(i * word_duration_ms)
                word_end_ms = segment.start_ms + int((i + 1) * word_duration_ms)

                all_words.append({
                    'text': word,
                    'start_ms': word_start_ms,
                    'end_ms': word_end_ms,
                    'confidence': segment.confidence
                })

        if not all_words:
            return []

        # Agora agrupar palavras em segmentos respeitando os limites
        optimized = []
        current_words = []
        current_start_ms = all_words[0]['start_ms']
        current_end_ms = all_words[0]['end_ms']
        current_confidence_sum = 0

        for word_data in all_words:
            potential_words = current_words + [word_data['text']]
            potential_text = " ".join(potential_words)
            potential_duration_ms = word_data['end_ms'] - current_start_ms
            potential_duration_sec = potential_duration_ms / 1000.0

            # Critérios para quebrar segmento
            should_break = (
                len(potential_words) > max_words_per_line or
                potential_duration_sec > max_duration or
                len(potential_text) > max_chars_per_line or
                (current_words and word_data['text'].endswith(('.', '!', '?', ',')))
            )

            if should_break and current_words:
                # Finalizar segmento atual
                current_text = " ".join(current_words)
                avg_confidence = current_confidence_sum / len(current_words) if current_words else 0

                optimized.append(SubtitleSegment(
                    start_ms=current_start_ms,
                    end_ms=current_end_ms,
                    text=current_text.strip(),
                    confidence=avg_confidence
                ))

                self.logger.debug(f"Segmento: '{current_text}' ({len(current_words)} palavras) - {current_start_ms}ms to {current_end_ms}ms")

                # Iniciar novo segmento
                current_words = [word_data['text']]
                current_start_ms = word_data['start_ms']
                current_end_ms = word_data['end_ms']
                current_confidence_sum = word_data['confidence']
            else:
                # Adicionar palavra ao segmento atual
                current_words = potential_words
                current_end_ms = word_data['end_ms']  # Estender até a última palavra
                current_confidence_sum += word_data['confidence']

        # Adicionar último segmento
        if current_words:
            current_text = " ".join(current_words)
            avg_confidence = current_confidence_sum / len(current_words) if current_words else 0
            optimized.append(SubtitleSegment(
                start_ms=current_start_ms,
                end_ms=current_end_ms,
                text=current_text.strip(),
                confidence=avg_confidence
            ))

            self.logger.debug(f"Último segmento: '{current_text}' ({len(current_words)} palavras) - {current_start_ms}ms to {current_end_ms}ms")

        self.logger.info(f"Segmentação concluída: {len(optimized)} segmentos otimizados")
        return optimized

