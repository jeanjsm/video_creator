# -*- coding: utf-8 -*-
"""
app/application/services/video_creation_service.py
Serviço de criação de vídeo atualizado com suporte a legendas
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from ...domain.models.timeline import Timeline, Track, Clip, RenderSettings
from ...domain.models.effects import EffectRef
from ...domain.models.subtitle import SubtitleStyle
from ...rendering.graph_builder import GraphBuilder
from ...rendering.cli_builder import CliBuilder
from ...rendering.runner import Runner
from ...rendering.batch_renderer import BatchRenderer
from ...rendering.simple_renderer import SimpleRenderer
from ...infra.media_io import MediaIO
from ...infra.logging import get_logger
from ...infra.paths import ffmpeg_bin
from .transcription_service import TranscriptionService
from fractions import Fraction


@dataclass
class VideoCreationRequest:
    """Requisição para criação de vídeo com suporte a legendas"""

    audio_path: Path
    images: List[Path]
    output_path: Path
    segment_duration: float = 3.0
    transition: Optional[str] = None
    encoder: str = "libx264"
    background_music_path: Optional[Path] = None
    background_music_volume: float = 0.2
    logo_path: Optional[Path] = None
    logo_position: str = "top_left"
    logo_opacity: float = 1.0
    logo_scale: float = 0.15
    overlays: Optional[List[Dict[str, Any]]] = None
    overlays_chromakey: Optional[List[Dict[str, Any]]] = None
    cover_path: Optional[Path] = None
    cover_opacity: float = 1.0
    cover_size: float = 1.0
    cover_position: str = "center"

    # Configurações de legenda
    enable_subtitles: bool = False
    subtitle_style: Optional[SubtitleStyle] = None
    vosk_model_path: Optional[Path] = None
    subtitle_confidence_threshold: float = 0.5
    subtitle_max_duration: float = 4.0


class VideoCreationService:
    """Serviço para criação de vídeos seguindo Clean Architecture"""

    def __init__(self):
        self.logger = get_logger("VideoCreationService")
        self.media_io = MediaIO()
        self.simple_renderer = SimpleRenderer()
        self.transcription_service = None

    def create_video(self, request: VideoCreationRequest) -> Path:
        """Cria vídeo a partir da requisição"""
        self.logger.info(
            "Iniciando criação de vídeo: saída=%s, imagens=%d, áudio=%s, legendas=%s",
            request.output_path,
            len(request.images),
            request.audio_path,
            request.enable_subtitles,
        )

        # 1. Inicializar serviço de transcrição se necessário
        if request.enable_subtitles:
            self._init_transcription_service(request.vosk_model_path)

        # 2. Construir timeline a partir dos inputs
        timeline = self._build_timeline(request)

        # 3. Construir render settings
        settings = self._build_render_settings(request)

        # 4. Renderizar usando SimpleRenderer (passar overlays_chromakey)
        result_path = self.simple_renderer.render(
            timeline, settings, request.output_path, overlays_chromakey=request.overlays_chromakey
        )

        self.logger.info("Vídeo criado com sucesso: %s", result_path)
        return result_path

    def _init_transcription_service(self, model_path: Optional[Path]):
        """Inicializa o serviço de transcrição"""
        # Usar ConfigAwareTranscriptionService que lê config.json
        from .config_aware_transcription_service import ConfigAwareTranscriptionService
        self.transcription_service = ConfigAwareTranscriptionService(model_path)

        if not self.transcription_service.is_available():
            self.logger.warning(
                "Serviço de transcrição não disponível. "
                "Verifique se o Vosk está instalado e o modelo está presente."
            )

    def _build_timeline(self, request: VideoCreationRequest) -> Timeline:
        """Constrói timeline a partir da requisição"""
        audio_duration = self.media_io.get_audio_duration(request.audio_path)

        # Criar clips de vídeo
        video_clips = []
        current_time = 0

        for i, image_path in enumerate(request.images):
            if audio_duration and current_time >= audio_duration:
                break

            clip_effects = self._get_image_effects(request, i)

            # Adicionar efeito de legenda no primeiro clip se habilitado
            if request.enable_subtitles and i == 0:
                subtitle_effect = self._create_subtitle_effect(request)
                if subtitle_effect:
                    clip_effects.append(subtitle_effect)

            # Adicionar chromas do config.json no primeiro clip
            if i == 0:
                chroma_effects = self._get_chroma_effects_from_config()
                clip_effects.extend(chroma_effects)

            clip = Clip(
                id=f"img_{i}",
                media_path=image_path,
                in_ms=0,
                out_ms=int(request.segment_duration * 1000),
                start_ms=int(current_time * 1000),
                effects=clip_effects,
            )
            video_clips.append(clip)
            current_time += request.segment_duration

        # Criar track de vídeo
        video_track = Track(id="video_main", kind="video", clips=video_clips)

        # Criar clips de áudio
        audio_clips = []
        if request.audio_path:
            audio_clip = Clip(
                id="narration",
                media_path=request.audio_path,
                in_ms=0,
                out_ms=int(audio_duration * 1000),
                start_ms=0,
            )
            audio_clips.append(audio_clip)

        if request.background_music_path:
            bg_clip = Clip(
                id="background_music",
                media_path=request.background_music_path,
                in_ms=0,
                out_ms=int(audio_duration * 1000),
                start_ms=0,
                effects=[
                    EffectRef(
                        name="volume",
                        params={"volume": request.background_music_volume},
                    )
                ],
            )
            audio_clips.append(bg_clip)

        # Criar track de áudio
        audio_track = Track(id="audio_main", kind="audio", clips=audio_clips)

        return Timeline(
            fps=Fraction(30, 1),
            resolution=(1280, 720),
            video=[video_track],
            audio=[audio_track],
        )

    def _create_subtitle_effect(self, request: VideoCreationRequest) -> Optional[EffectRef]:
        """Cria efeito de legenda baseado na transcrição do áudio"""
        if not self.transcription_service:
            self.logger.warning("Serviço de transcrição não foi inicializado")
            return None

        if not self.transcription_service.is_available():
            self.logger.warning("Serviço de transcrição não disponível para legendas")
            return None

        try:
            # Transcrever áudio
            self.logger.info("Transcrevendo áudio para legendas...")

            # Usar transcribe_with_config se disponível (ConfigAwareTranscriptionService)
            if hasattr(self.transcription_service, 'transcribe_with_config'):
                transcription, style = self.transcription_service.transcribe_with_config(
                    request.audio_path,
                    override_params={
                        "confidence_threshold": request.subtitle_confidence_threshold,
                        "max_segment_duration": request.subtitle_max_duration
                    }
                )
                # Usar estilo do request se especificado, senão usar do config
                final_style = request.subtitle_style or style
            else:
                # Fallback para TranscriptionService básico
                final_style = request.subtitle_style or SubtitleStyle()
                transcription = self.transcription_service.transcribe_audio(
                    request.audio_path,
                    confidence_threshold=request.subtitle_confidence_threshold,
                    max_segment_duration=request.subtitle_max_duration,
                    max_chars_per_line=final_style.max_chars_per_line,
                    max_words_per_line=final_style.max_words_per_line
                )

            if not transcription.segments:
                self.logger.warning("Nenhum segmento de fala encontrado para legendas")
                return None

            self.logger.info(f"Transcrição concluída: {len(transcription.segments)} segmentos")

            # Criar efeito de legenda
            return EffectRef(
                name="subtitle",
                params={
                    "segments": transcription.segments,
                    "style": final_style,
                },
                target="video"
            )

        except Exception as e:
            self.logger.error(f"Erro na transcrição para legendas: {e}")
            return None

    def _get_image_effects(
            self, request: VideoCreationRequest, index: int
    ) -> List[EffectRef]:
        """Retorna efeitos para aplicar em uma imagem"""
        effects = []

        # Adicionar transições se especificado
        if request.transition and index > 0:
            effects.append(EffectRef(name=request.transition, params={"duration": 1.0}))

        # Adicionar logo se especificado (apenas no primeiro clip para evitar duplicação)
        if request.logo_path and index == 0:
            effects.append(
                EffectRef(
                    name="logo",
                    params={
                        "path": str(request.logo_path),
                        "position": request.logo_position,
                        "scale": request.logo_scale,
                        "opacity": request.logo_opacity,
                    },
                )
            )

        # Adicionar overlays de vídeo se especificado (apenas no primeiro clip)
        if request.overlays and index == 0:
            from app.plugins.builtin.effects.overlay import OverlayEffect

            for i, overlay in enumerate(request.overlays):
                overlay_effect = OverlayEffect(
                    {
                        "path": overlay["path"],
                        "opacity": overlay.get("opacidade", 1.0),
                        "position": overlay.get("position", "center"),
                        "scale": overlay.get("scale", 1.0),
                    }
                )
                effects.append(
                    EffectRef(
                        name="overlay",
                        params={
                            "path": overlay_effect.path,
                            "opacity": overlay_effect.opacity,
                            "position": overlay_effect.position,
                            "scale": overlay_effect.scale,
                        },
                    )
                )

        # Adicionar capa se especificado (apenas no primeiro clip)
        if request.cover_path and index == 0:
            effects.append(
                EffectRef(
                    name="cover",
                    params={
                        "path": str(request.cover_path),
                        "position": request.cover_position,
                        "size": request.cover_size,
                        "opacity": request.cover_opacity,
                    },
                )
            )

        return effects

    def _get_chroma_effects_from_config(self) -> List[EffectRef]:
        """Obtém efeitos de chroma do config.json"""
        try:
            from ...infra.config import get_config
            config = get_config()
            chromas = config.get("chromas", [])

            if not chromas:
                return []

            self.logger.info(f"Encontrados {len(chromas)} chromas no config.json")

            chroma_effects = []
            for i, chroma in enumerate(chromas):
                chroma_path = chroma.get("path")
                if not chroma_path:
                    continue

                # Verificar se arquivo existe
                from pathlib import Path
                if not Path(chroma_path).exists():
                    self.logger.warning(f"Arquivo chroma não encontrado: {chroma_path}")
                    continue

                self.logger.info(f"Adicionando chroma: {chroma_path}")

                # Criar EffectRef para chroma
                chroma_effect = EffectRef(
                    name="chroma_overlay",
                    params={
                        "path": chroma_path,
                        "start": chroma.get("start", 0),
                        "opacity": chroma.get("opacity", 1.0),
                        "tolerance": chroma.get("tolerance", 0.2),
                        "position": chroma.get("position", "bottom_center"),
                        "size": chroma.get("size", 1.0),
                        "duration": chroma.get("duration"),  # Pode ser None
                        "colorkey": chroma.get("colorkey", "0x00FF00"),
                        "colorkey_similarity": chroma.get("colorkey_similarity", 0.35),
                        "colorkey_blend": chroma.get("colorkey_blend", 0.10),
                        "threshold": chroma.get("threshold", 0.03),
                        "ratio": chroma.get("ratio", 8),
                        "attack": chroma.get("attack", 5),
                        "release": chroma.get("release", 300),
                    },
                    target="video"
                )
                chroma_effects.append(chroma_effect)

            return chroma_effects

        except Exception as e:
            self.logger.error(f"Erro ao ler chromas do config.json: {e}")
            return []

    def _build_render_settings(self, request: VideoCreationRequest) -> RenderSettings:
        """Constrói configurações de renderização"""
        return RenderSettings(
            container="mp4",
            vcodec=request.encoder,
            acodec="aac",
            crf=23,
            preset="p5" if "nvenc" in request.encoder else "medium",
            audio_bitrate="192k",
            hwaccel="cuda" if "nvenc" in request.encoder else None,
            ffmpeg_path=ffmpeg_bin(),
        )
