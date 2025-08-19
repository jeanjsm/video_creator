# -*- coding: utf-8 -*-
"""
app/application/services/config_aware_transcription_service.py
Extensão do TranscriptionService que lê configurações do config.json
"""

from typing import Optional, Dict, Any
from pathlib import Path

from .transcription_service import TranscriptionService
from ...domain.models.subtitle import SubtitleStyle, TranscriptionResult
from ...infra.config import get_config
from ...infra.logging import get_logger


class ConfigAwareTranscriptionService(TranscriptionService):
    """
    Serviço de transcrição que integra configurações do config.json
    """

    def __init__(self, model_path: Optional[Path] = None):
        # Carregar configurações
        self.config = get_config()
        self.logger = get_logger("ConfigAwareTranscriptionService")

        # Usar model_path do config se não especificado
        if model_path is None:
            config_model = self.config.get("subtitles", {}).get("vosk_model_path")
            if config_model:
                model_path = Path(config_model)

        super().__init__(model_path)

    def is_enabled_in_config(self) -> bool:
        """Verifica se legendas estão habilitadas no config"""
        return self.config.get("subtitles", {}).get("enabled", False)

    def get_config_style(self, preset_name: str = None) -> SubtitleStyle:
        """
        Obtém estilo de legenda do config.json

        Args:
            preset_name: Nome do preset (youtube, instagram, tiktok) ou None para padrão
        """
        subtitles_config = self.config.get("subtitles", {})

        if preset_name and preset_name in subtitles_config.get("presets", {}):
            # Usar preset específico
            style_config = subtitles_config["presets"][preset_name]
            self.logger.info(f"Usando preset de legenda: {preset_name}")
        else:
            # Usar estilo padrão
            style_config = subtitles_config.get("style", {})
            self.logger.info("Usando estilo padrão de legenda")

        # Criar SubtitleStyle com configurações do config.json
        return SubtitleStyle(
            font_size=style_config.get("font_size", 24),
            font_color=style_config.get("font_color", "white"),
            background_color=style_config.get("background_color", "black@0.5"),
            position=style_config.get("position", "bottom_center"),
            margin_bottom=style_config.get("margin_bottom", 50),
            max_chars_per_line=style_config.get("max_chars_per_line", 60),
            outline_width=style_config.get("outline_width", 2),
            outline_color=style_config.get("outline_color", "black"),
        )

    def get_config_transcription_params(self) -> Dict[str, Any]:
        """Obtém parâmetros de transcrição do config.json"""
        subtitles_config = self.config.get("subtitles", {})

        return {
            "confidence_threshold": subtitles_config.get("confidence_threshold", 0.5),
            "max_segment_duration": subtitles_config.get("max_segment_duration", 4.0),
        }

    def transcribe_with_config(
            self,
            audio_path: Path,
            preset_name: str = None,
            override_params: Dict[str, Any] = None
    ) -> tuple[TranscriptionResult, SubtitleStyle]:
        """
        Transcreve áudio usando configurações do config.json

        Args:
            audio_path: Caminho do áudio
            preset_name: Nome do preset de estilo
            override_params: Parâmetros para sobrescrever configurações

        Returns:
            Tupla com (resultado da transcrição, estilo aplicado)
        """
        if not self.is_available():
            raise RuntimeError("Vosk não está disponível ou modelo não encontrado")

        # Obter parâmetros de transcrição
        params = self.get_config_transcription_params()
        if override_params:
            params.update(override_params)

        self.logger.info(
            f"Transcrevendo com config: confidence={params['confidence_threshold']}, "
            f"max_duration={params['max_segment_duration']}"
        )

        # Realizar transcrição
        transcription = self.transcribe_audio(
            audio_path,
            confidence_threshold=params["confidence_threshold"],
            max_segment_duration=params["max_segment_duration"]
        )

        # Obter estilo
        style = self.get_config_style(preset_name)

        return transcription, style

    def list_available_presets(self) -> Dict[str, Dict[str, Any]]:
        """Lista presets disponíveis no config"""
        return self.config.get("subtitles", {}).get("presets", {})

    def validate_config(self) -> tuple[bool, list[str]]:
        """
        Valida configurações de legenda no config.json

        Returns:
            Tupla com (é_válido, lista_de_erros)
        """
        errors = []
        subtitles_config = self.config.get("subtitles", {})

        # Verificar se configuração de legendas existe
        if not subtitles_config:
            errors.append("Seção 'subtitles' não encontrada no config.json")
            return False, errors

        # Verificar modelo Vosk
        model_path = subtitles_config.get("vosk_model_path")
        if not model_path:
            errors.append("'vosk_model_path' não especificado")
        else:
            model_path_obj = Path(model_path)
            if not model_path_obj.exists():
                errors.append(f"Modelo Vosk não encontrado: {model_path}")
            elif not self._verify_model_structure(model_path_obj):
                errors.append(f"Estrutura do modelo Vosk inválida: {model_path}")

        # Verificar parâmetros numéricos
        confidence = subtitles_config.get("confidence_threshold", 0.5)
        if not (0.0 <= confidence <= 1.0):
            errors.append(f"confidence_threshold deve estar entre 0.0 e 1.0, encontrado: {confidence}")

        max_duration = subtitles_config.get("max_segment_duration", 4.0)
        if not (0.5 <= max_duration <= 30.0):
            errors.append(f"max_segment_duration deve estar entre 0.5 e 30.0, encontrado: {max_duration}")

        # Verificar estilo padrão
        style_config = subtitles_config.get("style", {})
        if style_config:
            style_errors = self._validate_style_config(style_config, "style")
            errors.extend(style_errors)

        # Verificar presets
        presets = subtitles_config.get("presets", {})
        for preset_name, preset_config in presets.items():
            preset_errors = self._validate_style_config(preset_config, f"presets.{preset_name}")
            errors.extend(preset_errors)

        return len(errors) == 0, errors

    def _validate_style_config(self, style_config: Dict[str, Any], path: str) -> list[str]:
        """Valida configuração de estilo"""
        errors = []

        # Validar font_size
        font_size = style_config.get("font_size")
        if font_size is not None and not (8 <= font_size <= 100):
            errors.append(f"{path}.font_size deve estar entre 8 e 100")

        # Validar position
        position = style_config.get("position")
        valid_positions = ["bottom_center", "top_center", "center", "bottom_left", "bottom_right"]
        if position is not None and position not in valid_positions:
            errors.append(f"{path}.position deve ser um de: {valid_positions}")

        # Validar margin_bottom
        margin = style_config.get("margin_bottom")
        if margin is not None and not (0 <= margin <= 200):
            errors.append(f"{path}.margin_bottom deve estar entre 0 e 200")

        # Validar max_chars_per_line
        max_chars = style_config.get("max_chars_per_line")
        if max_chars is not None and not (10 <= max_chars <= 100):
            errors.append(f"{path}.max_chars_per_line deve estar entre 10 e 100")

        return errors

    def _verify_model_structure(self, model_path: Path) -> bool:
        """Verifica se estrutura do modelo Vosk está correta"""
        required_files = ["am", "conf", "graph"]
        return all((model_path / req_file).exists() for req_file in required_files)


def create_transcription_service_from_config() -> ConfigAwareTranscriptionService:
    """Factory function para criar serviço baseado no config"""
    return ConfigAwareTranscriptionService()