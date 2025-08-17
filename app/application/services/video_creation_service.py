# -*- coding: utf-8 -*-
"""
Serviço de criação de vídeo - Clean         # 3. Renderizar usando BatchRenderer
        result_path = self.batch_renderer.render(timeline, settings, request.output_path)

        self.logger.info("Vídeo criado com sucesso: %s", result_path)
        return result_path"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from ...domain.models.timeline import Timeline, Track, Clip, RenderSettings
from ...domain.models.effects import EffectRef
from ...rendering.graph_builder import GraphBuilder
from ...rendering.cli_builder import CliBuilder
from ...rendering.runner import Runner
from ...rendering.batch_renderer import BatchRenderer
from ...rendering.simple_renderer import SimpleRenderer
from ...infra.media_io import MediaIO
from ...infra.logging import get_logger
from ...infra.paths import ffmpeg_bin
from fractions import Fraction


@dataclass
class VideoCreationRequest:
    """Requisição para criação de vídeo"""

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


class VideoCreationService:
    """Serviço para criação de vídeos seguindo Clean Architecture"""

    def __init__(self):
        self.logger = get_logger("VideoCreationService")
        self.media_io = MediaIO()
        self.simple_renderer = SimpleRenderer()  # Usar renderizador simples

    def create_video(self, request: VideoCreationRequest) -> Path:
        """Cria vídeo a partir da requisição"""
        self.logger.info(
            "Iniciando criação de vídeo: saída=%s, imagens=%d, áudio=%s",
            request.output_path,
            len(request.images),
            request.audio_path,
        )

        # 1. Construir timeline a partir dos inputs
        timeline = self._build_timeline(request)

        # 2. Construir render settings
        settings = self._build_render_settings(request)

        # 3. Renderizar usando SimpleRenderer
        result_path = self.simple_renderer.render(
            timeline, settings, request.output_path
        )

        self.logger.info("Vídeo criado com sucesso: %s", result_path)
        return result_path

    def _build_timeline(self, request: VideoCreationRequest) -> Timeline:
        """Constrói timeline a partir da requisição"""
        audio_duration = self.media_io.get_audio_duration(request.audio_path)

        # Criar clips de vídeo
        video_clips = []
        current_time = 0

        for i, image_path in enumerate(request.images):
            if audio_duration and current_time >= audio_duration:
                break

            clip = Clip(
                id=f"img_{i}",
                media_path=image_path,
                in_ms=0,
                out_ms=int(request.segment_duration * 1000),
                start_ms=int(current_time * 1000),
                effects=self._get_image_effects(request, i),
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
            for i, overlay in enumerate(request.overlays):
                effects.append(
                    EffectRef(
                        name="overlay",
                        params={
                            "path": overlay["path"],
                            "opacity": overlay.get("opacidade", 1.0),
                        },
                    )
                )

        # Adicionar overlays chromakey de vídeo se especificado (apenas no primeiro clip)
        if request.overlays_chromakey and index == 0:
            self.logger.info(
                f"[DEBUG] Adicionando {len(request.overlays_chromakey)} overlay(s) chromakey ao primeiro clip"
            )
            for overlay in request.overlays_chromakey:
                self.logger.info(f"[DEBUG] Overlay chromakey: {overlay}")
                effects.append(
                    EffectRef(
                        name="overlay_chromakey",
                        params={
                            "path": overlay["path"],
                            "start": overlay.get("start", 0.0),
                            "position": overlay.get("position", "center"),
                            "chromakey": overlay.get("chromakey", None),
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
