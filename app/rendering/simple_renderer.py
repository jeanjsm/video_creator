# -*- coding: utf-8 -*-
"""
app/rendering/simple_renderer.py
SimpleRenderer atualizado com suporte a legendas
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import tempfile
import subprocess
import os

from ..domain.models.timeline import Timeline, Track, Clip, RenderSettings
from ..infra.logging import get_logger
from ..infra.paths import ffmpeg_bin
from .graph_builder import GraphBuilder, FilterGraph
from .cli_builder import CliBuilder
from .runner import Runner
from app.plugins.builtin.effects.overlay import OverlayEffect
from app.plugins.builtin.effects.logo import LogoEffect
from app.plugins.builtin.effects.cover import CoverEffect
from app.plugins.builtin.effects.chroma_overlay import ChromaOverlayEffect
from app.plugins.builtin.effects.subtitle import SubtitleEffect


class SimpleRenderer:
    """
    Renderizador seguindo Clean Architecture com suporte a legendas

    Pipeline:
    1. Timeline -> GraphBuilder -> FilterGraph
    2. FilterGraph -> CliBuilder -> list[str]
    3. list[str] -> Runner -> CompletedProcess
    """

    def __init__(self):
        self.logger = get_logger("SimpleRenderer")
        self.graph_builder = GraphBuilder()
        self.cli_builder = CliBuilder()
        self.runner = Runner()

    def render(
            self, timeline: Timeline, settings: RenderSettings, output_path: Path, overlays_chromakey: Optional[List[Dict[str, Any]]] = None
    ) -> Path:
        """
        Renderiza vídeo usando pipeline Clean Architecture

        Etapas:
        1. Criar vídeo das imagens (concat approach)
        2. Adicionar áudio e efeitos visuais (filtergraph approach)
        3. Adicionar legendas se especificado
        """
        self.logger.info("Iniciando renderização simples")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Etapa 1: Criar vídeo base das imagens
                video_temp = temp_path / "video_temp.mp4"
                self._create_video_from_images(timeline, video_temp, settings)

                # Etapa 2: Adicionar áudio e efeitos visuais (incluindo overlays chromakey)
                self._add_audio_and_effects(video_temp, timeline, output_path, settings, overlays_chromakey)

                return output_path

        except Exception as e:
            self.logger.error(f"Erro na renderização: {e}")
            raise

    def _create_video_from_images(
            self, timeline: Timeline, output_path: Path, settings: RenderSettings
    ):
        """Cria vídeo das imagens usando concat approach"""

        video_track = timeline.video[0] if timeline.video else None
        if not video_track:
            raise ValueError("Nenhuma track de vídeo encontrada")

        clips = video_track.clips

        # Buscar parâmetro de transição
        transition = getattr(settings, "transition", None)
        if not transition:
            # Procurar efeito de transição em qualquer clip (exceto o primeiro)
            for c in clips[1:]:
                for eff in c.effects:
                    if eff.name not in ("logo", "overlay", "volume", "subtitle"):
                        transition = eff.name
                        break
                if transition:
                    break
        if not transition:
            transition = "fade"

        self.logger.info(
            f"Criando slideshow simples (transição: {transition})"
        )
        self._create_simple_slideshow(
            clips, output_path, settings, transition=transition
        )

    def _create_simple_slideshow(
            self,
            clips: List[Clip],
            output_path: Path,
            settings: RenderSettings,
            transition: str = "fade",
    ):
        """Cria slideshow simples com transição xfade entre imagens"""
        self.logger.info(
            f"Criando slideshow com transição '{transition}' entre {len(clips)} imagens"
        )

        # Carregar resolução do config.json
        import json

        config_path = Path(__file__).parents[2] / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            resolution_str = config_data.get("resolution", "1280x720")
        else:
            resolution_str = "1280x720"
        try:
            width, height = map(int, resolution_str.lower().split("x"))
        except Exception:
            width, height = 1280, 720

        transition_duration = 1.0
        segment_duration = (clips[0].out_ms - clips[0].in_ms) / 1000.0
        if segment_duration > 2:
            transition_duration = min(1.0, segment_duration * 0.3)

        cmd = [str(ffmpeg_bin()), "-y"]
        for clip in clips:
            cmd.extend(
                ["-loop", "1", "-t", str(segment_duration), "-i", str(clip.media_path)]
            )

        filter_parts = []
        # Normalizar todas as imagens para a resolução do config
        for i in range(len(clips)):
            filter_parts.append(
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[v{i}]"
            )

        # Montar cadeia de transições
        import random
        from app.plugins.builtin.transitions.registry import TRANSITIONS

        transition_names = [k for k in TRANSITIONS.keys() if k != "none"]

        if len(clips) == 1:
            final_output = f"[v0]"
        else:
            prev = f"[v0]"
            for i in range(1, len(clips)):
                offset = (segment_duration - transition_duration) * i
                if transition == "random":
                    tname = random.choice(transition_names)
                    from app.plugins.builtin.transitions.registry import get_transition
                    transition_obj = get_transition(tname)
                    self.logger.info(
                        f"Transição aleatória escolhida para par {i}: {tname}"
                    )
                else:
                    from app.plugins.builtin.transitions.registry import get_transition
                    transition_obj = get_transition(transition)
                filter_str = transition_obj.build_filter(
                    duration=transition_duration, offset=offset
                )
                filter_parts.append(f"{prev}[v{i}]{filter_str}[x{i}]")
                prev = f"[x{i}]"
            final_output = prev

        cmd.extend(["-filter_complex", ";".join(filter_parts)])
        cmd.extend(["-map", final_output])
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                str(output_path),
            ]
        )

        try:
            self.logger.info(f"Executando comando direto: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                ),
            )
        except Exception as e:
            self.logger.error(f"Erro ao criar slideshow: {e}")
            raise RuntimeError(f"Erro ao criar slideshow: {e}")

    def _add_audio_and_effects(
            self,
            video_path: Path,
            timeline: Timeline,
            output_path: Path,
            settings: RenderSettings,
            overlays_chromakey: Optional[List[Dict[str, Any]]] = None,
    ):
        """Adiciona áudio e efeitos visuais (incluindo legendas e overlays chromakey)"""

        audio_tracks = timeline.audio
        if not audio_tracks:
            # Sem áudio, apenas copiar vídeo
            import shutil
            shutil.copy2(video_path, output_path)
            return

        self.logger.info("Adicionando áudio e efeitos ao vídeo")

        # Detectar efeitos visuais no primeiro video clip
        video_track = timeline.video[0] if timeline.video else None
        visual_effects = []
        subtitle_effect = None
        chroma_effects = []

        if video_track and video_track.clips:
            for effect in video_track.clips[0].effects:
                if effect.name == "subtitle":
                    subtitle_effect = effect
                elif effect.name == "chroma_overlay":
                    chroma_effects.append(effect)
                elif effect.name in ["logo", "overlay", "cover"]:
                    visual_effects.append(effect)

        # Adicionar overlays_chromakey passados como parâmetro
        if overlays_chromakey:
            self.logger.info(f"Processando {len(overlays_chromakey)} overlays chromakey do request")
            for i, overlay in enumerate(overlays_chromakey):
                # Converter para EffectRef para compatibilidade
                from ..domain.models.effects import EffectRef
                chroma_effect = EffectRef(
                    name="chroma_overlay",
                    params={
                        "path": overlay["path"],
                        "start": overlay.get("start", 0.0),
                        "position": overlay.get("position", "center"),
                        "chromakey": overlay.get("chromakey", "green"),
                    },
                    target="video"
                )
                chroma_effects.append(chroma_effect)

        # Se há efeitos complexos OU legendas OU chromas, usar implementação estendida
        if visual_effects or subtitle_effect or chroma_effects:
            self.logger.info(
                f"Efeitos detectados - Visual: {len(visual_effects)}, "
                f"Legendas: {'Sim' if subtitle_effect else 'Não'}, "
                f"Chromas: {len(chroma_effects)}"
            )
            self._add_audio_and_effects_extended(
                video_path, timeline, output_path, settings, subtitle_effect, chroma_effects
            )
            return

        # Pipeline simples para casos sem efeitos visuais complexos
        self._add_audio_simple(video_path, timeline, output_path, settings)

    def _add_audio_simple(
            self,
            video_path: Path,
            timeline: Timeline,
            output_path: Path,
            settings: RenderSettings,
    ):
        """Pipeline simples para adicionar apenas áudio"""
        audio_tracks = timeline.audio
        cmd = [str(ffmpeg_bin()), "-y", "-i", str(video_path)]

        # Adicionar inputs de áudio
        audio_inputs = []
        for track in audio_tracks:
            for clip in track.clips:
                cmd.extend(["-i", str(clip.media_path)])
                audio_inputs.append(len(audio_inputs) + 1)

        # Mapear streams
        if len(audio_inputs) == 1:
            cmd.extend(["-map", "0:v", "-map", "1:a"])
            cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"])
        else:
            # Múltiplos áudios - mixar
            audio_filter = f"[1:a]volume=1.0[narr];[2:a]volume=0.2[bg];[narr][bg]amix=inputs=2:duration=first[aout]"
            cmd.extend(["-filter_complex", audio_filter])
            cmd.extend(["-map", "0:v", "-map", "[aout]"])
            cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"])

        cmd.extend(["-movflags", "+faststart", str(output_path)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                ),
            )
            if result.returncode != 0:
                raise RuntimeError(f"Falha na mixagem de áudio: {result.stderr}")
        except Exception as e:
            raise RuntimeError(f"Erro na mixagem de áudio: {e}")

    def _add_audio_and_effects_extended(
            self,
            video_path: Path,
            timeline: Timeline,
            output_path: Path,
            settings: RenderSettings,
            subtitle_effect: Optional[object] = None,
            chroma_effects: List[object] = None,
    ):
        """Pipeline estendido com efeitos visuais e legendas"""

        audio_tracks = timeline.audio
        audio_duration = 0.0
        if audio_tracks and audio_tracks[0].clips:
            first_clip = audio_tracks[0].clips[0]
            audio_duration = (first_clip.out_ms - first_clip.in_ms) / 1000.0

        cmd = [str(ffmpeg_bin()), "-y", "-i", str(video_path)]

        # Adicionar inputs de áudio
        audio_inputs = []
        for track in audio_tracks:
            for clip in track.clips:
                cmd.extend(["-i", str(clip.media_path)])
                audio_inputs.append(len(audio_inputs) + 1)

        # Coletar efeitos visuais do primeiro clip
        video_track = timeline.video[0] if timeline.video else None
        visual_effects = []

        if video_track and video_track.clips:
            for effect in video_track.clips[0].effects:
                if effect.name in ["logo", "overlay", "cover"]:
                    visual_effects.append(effect)

        # Adicionar inputs para efeitos visuais e chromas
        input_counter = len(audio_inputs) + 1
        effect_inputs = {}

        # Adicionar inputs para efeitos visuais tradicionais
        for effect in visual_effects:
            effect_path = effect.params.get("path")
            if effect_path and Path(effect_path).exists():
                if effect.name == "overlay":
                    overlay_duration = self._get_video_duration_legacy(Path(effect_path))
                    if overlay_duration and audio_duration:
                        loops_needed = max(1, int((audio_duration / overlay_duration) + 1))
                        cmd.extend(["-stream_loop", str(loops_needed), "-i", str(effect_path)])
                    else:
                        cmd.extend(["-stream_loop", "8", "-i", str(effect_path)])
                else:
                    cmd.extend(["-i", str(effect_path)])
                effect_inputs[effect.name] = input_counter
                input_counter += 1

        # Adicionar inputs para efeitos de chroma
        chroma_inputs = {}
        if chroma_effects:
            self.logger.info(f"Adicionando {len(chroma_effects)} inputs para chromas")
            for i, chroma_effect in enumerate(chroma_effects):
                chroma_path = chroma_effect.params.get("path")
                if chroma_path and Path(chroma_path).exists():
                    cmd.extend(["-i", str(chroma_path)])
                    chroma_inputs[f"chroma_{i}"] = input_counter
                    input_counter += 1
                    self.logger.info(f"Chroma {i}: {chroma_path} -> input {input_counter-1}")

        # Construir filtros
        filter_parts = []
        current_video = "[0:v]"

        # Aplicar efeitos visuais primeiro
        for effect in visual_effects:
            if effect.name == "overlay" and effect.name in effect_inputs:
                input_idx = effect_inputs[effect.name]
                overlay_input = f"[{input_idx}:v]"
                overlay_effect_obj = OverlayEffect(effect.params)
                input_label = current_video.strip("[]")
                overlay_label = overlay_input.strip("[]")
                output_label = "overlay_out"
                filter_snippet = overlay_effect_obj.build_filter(
                    input_label, overlay_label, output_label
                )
                filter_parts.append(filter_snippet)
                current_video = f"[{output_label}]"
            elif effect.name == "logo" and effect.name in effect_inputs:
                input_idx = effect_inputs[effect.name]
                logo_input = f"[{input_idx}:v]"
                logo_effect_obj = LogoEffect(effect.params)
                input_label = current_video.strip("[]")
                logo_label = logo_input.strip("[]")
                output_label = "logo_out"
                filter_snippet = logo_effect_obj.build_filter(
                    input_label, logo_label, output_label
                )
                filter_parts.append(filter_snippet)
                current_video = f"[{output_label}]"
            elif effect.name == "cover" and effect.name in effect_inputs:
                input_idx = effect_inputs[effect.name]
                cover_input = f"[{input_idx}:v]"
                cover_effect_obj = CoverEffect(effect.params)
                input_label = current_video.strip("[]")
                cover_label = cover_input.strip("[]")
                output_label = "cover_out"
                filter_snippet = cover_effect_obj.build_filter(
                    input_label, cover_label, output_label
                )
                filter_parts.append(filter_snippet)
                current_video = f"[{output_label}]"

        # Aplicar efeitos de chroma após os efeitos visuais tradicionais
        if chroma_effects:
            self.logger.info(f"Aplicando {len(chroma_effects)} efeitos de chroma")
            for i, chroma_effect in enumerate(chroma_effects):
                chroma_key = f"chroma_{i}"
                if chroma_key in chroma_inputs:
                    input_idx = chroma_inputs[chroma_key]

                    # Usar ChromaOverlayEffect ao invés de implementação manual
                    chroma_effect_obj = ChromaOverlayEffect(chroma_effect.params)

                    main_video_label = current_video.strip("[]")
                    overlay_label = f"{input_idx}:v"
                    output_label = f"chroma_out_{i}"

                    # Verificar se há áudio para ducking
                    main_audio_label = None
                    overlay_audio_label = None

                    # Se temos áudio e o overlay tem áudio, aplicar ducking
                    if len(audio_inputs) > 0:
                        # Verificar se o overlay tem stream de áudio
                        overlay_path = chroma_effect.params.get("path")
                        if overlay_path and self._has_audio_stream(Path(overlay_path)):
                            main_audio_label = f"{audio_inputs[0]}:a" if audio_inputs else None
                            overlay_audio_label = f"{input_idx}:a"

                    chroma_filter = chroma_effect_obj.build_filter(
                        main_video_label=main_video_label,
                        overlay_label=overlay_label,
                        main_audio_label=main_audio_label,
                        overlay_audio_label=overlay_audio_label,
                        v_out=output_label,
                        a_out=f"chroma_audio_{i}" if main_audio_label and overlay_audio_label else None
                    )

                    filter_parts.append(chroma_filter)
                    current_video = f"[{output_label}]"

                    # Se foi aplicado ducking de áudio, atualizar a referência de áudio
                    if main_audio_label and overlay_audio_label:
                        # Substituir a primeira entrada de áudio pela saída com ducking
                        audio_output = f"[chroma_audio_{i}]"
                        # Marcar que já temos áudio processado
                        audio_inputs = []  # Limpar para evitar processamento duplo

                    self.logger.info(f"Chroma {i}: usando ChromaOverlayEffect com parâmetros {chroma_effect.params}")

        # Aplicar legendas por último (depois de todos os outros efeitos)
        if subtitle_effect:
            self.logger.info("Aplicando efeito de legendas")
            segments = subtitle_effect.params.get("segments", [])
            style = subtitle_effect.params.get("style", None)

            if segments:
                subtitle_effect_obj = SubtitleEffect(segments, style)
                input_label = current_video.strip("[]")
                output_label = "subtitle_out"
                subtitle_filter = subtitle_effect_obj.build_filter(input_label, output_label)
                filter_parts.append(subtitle_filter)
                current_video = f"[{output_label}]"

        # Filtros de áudio
        audio_output = None
        if len(audio_inputs) == 1:
            audio_output = f"{audio_inputs[0]}:a"
        elif len(audio_inputs) > 1:
            for i, input_idx in enumerate(audio_inputs):
                volume = "1.0" if i == 0 else "0.2"
                filter_parts.append(f"[{input_idx}:a]volume={volume}[a{i}]")
            mix_inputs = "".join([f"[a{i}]" for i in range(len(audio_inputs))])
            filter_parts.append(
                f"{mix_inputs}amix=inputs={len(audio_inputs)}:duration=first[aout]"
            )
            audio_output = "[aout]"

        # Se não temos audio_inputs mas existe audio_output definido pelo chroma overlay, mantê-lo
        # (isso acontece quando o ducking foi aplicado)

        # Aplicar filtros se necessário
        if filter_parts:
            cmd.extend(["-filter_complex", ";".join(filter_parts)])
            cmd.extend(["-map", current_video])
            if audio_output:
                cmd.extend(["-map", audio_output])
        else:
            cmd.extend(["-map", "0:v"])
            if audio_inputs:
                cmd.extend(["-map", f"{audio_inputs[0]}:a"])

        # Configurações finais
        cmd.extend([
            "-c:v", "libx264" if filter_parts else "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-t", str(audio_duration),
            str(output_path),
        ])

        # Executar
        try:
            self.runner.run(cmd, timeout=300)  # 5 minutos para efeitos + legendas
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Erro FFmpeg: {e.stderr}")
            raise RuntimeError(f"FFmpeg falhou: {e.stderr}")
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout na renderização com efeitos")
            raise RuntimeError("Timeout na renderização")

    def _has_audio_stream(self, video_path: Path) -> bool:
        """Verifica se o arquivo de vídeo tem stream de áudio"""
        try:
            cmd = [
                str(ffmpeg_bin()),
                "-v", "quiet",
                "-show_streams",
                "-select_streams", "a",
                "-of", "csv=p=0",
                str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0 and result.stdout.strip()
        except Exception:
            return False

    def _get_video_duration_legacy(self, video_path: Path) -> Optional[float]:
        """Obtém duração de vídeo (método legacy)"""
        try:
            cmd = [
                str(ffmpeg_bin()),
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            return None
        except Exception:
            return None
