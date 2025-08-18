# -*- coding: utf-8 -*-
"""
SimpleRenderer - Renderizador que segue Clean Architecture
Pipeline: Timeline -> FilterGraph -> FFmpeg Command -> Execution
"""


from pathlib import Path
from typing import List, Optional
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


class SimpleRenderer:
    """
    Renderizador seguindo Clean Architecture

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
        self, timeline: Timeline, settings: RenderSettings, output_path: Path
    ) -> Path:
        """
        Renderiza vídeo usando pipeline Clean Architecture

        Etapas:
        1. Criar vídeo das imagens (concat approach)
        2. Adicionar áudio e efeitos visuais (filtergraph approach)
        """
        self.logger.info("Iniciando renderização simples")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Etapa 1: Criar vídeo base das imagens
                video_temp = temp_path / "video_temp.mp4"
                self._create_video_from_images(timeline, video_temp, settings)

                # Etapa 2: Adicionar áudio e efeitos visuais
                self._add_audio_and_effects(video_temp, timeline, output_path, settings)

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

        # Buscar parâmetro de transição: settings -> efeito do primeiro clip -> fallback
        transition = getattr(settings, "transition", None)
        if not transition:
            # Procurar efeito de transição em qualquer clip (exceto o primeiro)
            for c in clips[1:]:
                for eff in c.effects:
                    if eff.name not in ("logo", "overlay", "volume"):
                        transition = eff.name
                        break
                if transition:
                    break
        if not transition:
            transition = "fade"

        self.logger.info(
            f"Forçando slideshow simples para evitar travamentos (transição: {transition})"
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

        transition_duration = 1.0  # padrão 1s
        segment_duration = (clips[0].out_ms - clips[0].in_ms) / 1000.0
        if segment_duration > 2:
            transition_duration = min(1.0, segment_duration * 0.3)

        from ..infra.paths import ffmpeg_bin
        import subprocess
        from app.plugins.builtin.transitions.registry import get_transition

        cmd = [str(ffmpeg_bin()), "-y"]
        for clip in clips:
            cmd.extend(
                ["-loop", "1", "-t", str(segment_duration), "-i", str(clip.media_path)]
            )

        filter_parts = []
        # Normalizar todas as imagens
        for i in range(len(clips)):
            filter_parts.append(
                f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2[v{i}]"
            )

        # Montar cadeia de transições usando classes
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
                    transition_obj = get_transition(tname)
                    self.logger.info(
                        f"Transição aleatória escolhida para par {i}: {tname}"
                    )
                else:
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
    ):
        """Adiciona áudio e efeitos visuais usando pipeline da arquitetura"""

        audio_tracks = timeline.audio
        if not audio_tracks:
            # Sem áudio, apenas copiar vídeo
            import shutil

            shutil.copy2(video_path, output_path)
            return

        self.logger.info("Adicionando áudio ao vídeo")

        # Tentar migrar para pipeline Clean Architecture para casos simples
        # - Construímos um FilterGraph mínimo com video + audios
        # - Se houver efeitos visuais complexos (logo/overlay/chroma), usamos fallback legacy

        # Detectar efeitos visuais no primeiro video clip
        video_track = timeline.video[0] if timeline.video else None
        visual_effects = []
        if video_track and video_track.clips:
            for effect in video_track.clips[0].effects:
                if effect.name in ["logo", "overlay", "cover"]:
                    visual_effects.append(effect)

        if visual_effects:
            # Casos complexos continuam usando implementação legacy por agora
            self.logger.info(
                "Efeitos visuais detectados — usando fallback legacy para garantir compatibilidade"
            )
            self._add_audio_to_video_legacy(video_path, timeline, output_path, settings)
            return

        # Sem efeitos visuais complexos — usar GraphBuilder minimal + CliBuilder + Runner
        graph = FilterGraph()
        # input 0 = vídeo já renderizado
        graph.add_input(video_path)

        # adicionar inputs de áudio
        audio_inputs = []
        for track in timeline.audio:
            for clip in track.clips:
                graph.add_input(clip.media_path)
                audio_inputs.append(len(graph.inputs) - 1)  # índice do input

        # Construir filtros de áudio semelhantes ao GraphBuilder
        if len(audio_inputs) == 1:
            graph.add_filter(f"[{audio_inputs[0]}:a]volume=1.0[aout]")
        elif len(audio_inputs) > 1:
            # Primeiro é narração, segundo é música de fundo
            narration_idx = audio_inputs[0]
            bg_idx = audio_inputs[1]
            graph.add_filter(f"[{narration_idx}:a]volume=1.0[narr]")

            # tentar detectar volume em efeitos do bg (se existir)
            bg_volume = 0.2
            try:
                bg_clip = timeline.audio[1].clips[0]
                for eff in getattr(bg_clip, "effects", []):
                    if eff.name == "volume":
                        bg_volume = eff.params.get("volume", bg_volume)
                        break
            except Exception:
                pass

            graph.add_filter(f"[{bg_idx}:a]volume={bg_volume}[bg]")
            graph.add_filter(
                "[narr][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )

        # Construir comando manualmente para evitar problemas com filtergraph
        from ..infra.paths import ffmpeg_bin

        cmd = [str(ffmpeg_bin()), "-y"]

        # Adicionar inputs
        cmd.extend(["-i", str(video_path)])
        for track in timeline.audio:
            for clip in track.clips:
                cmd.extend(["-i", str(clip.media_path)])

        # Para casos simples, mapear diretamente
        if len(audio_inputs) == 1:
            # Um áudio apenas
            cmd.extend(["-map", "0:v", "-map", "1:a"])
            cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"])
        else:
            # Múltiplos áudios - usar filtro de áudio simples
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

            if result.returncode == 0:
                self.logger.info("Áudio adicionado com sucesso")
            else:
                self.logger.error(f"Erro na mixagem de áudio: {result.stderr}")
                raise RuntimeError(f"Falha na mixagem de áudio: {result.stderr}")

        except subprocess.TimeoutExpired:
            self.logger.error("Timeout na mixagem de áudio")
            raise RuntimeError("Timeout na mixagem de áudio")
        except Exception as e:
            self.logger.error(f"Erro inesperado na mixagem: {e}")
            raise RuntimeError(f"Erro na mixagem de áudio: {e}")

    def _build_simple_slideshow_command(
        self,
        inputs: List[Path],
        duration: float,
        output_path: Path,
        settings: RenderSettings,
    ) -> List[str]:
        """Constrói comando para slideshow simples usando CliBuilder pattern"""
        from ..infra.paths import ffmpeg_bin

        cmd = [str(ffmpeg_bin()), "-y"]

        # Adicionar todas as imagens como inputs
        for input_path in inputs:
            cmd.extend(["-loop", "1", "-t", str(duration), "-i", str(input_path)])

        # Filtro de vídeo simples
        filter_parts = []

        # Normalizar todas as imagens
        for i in range(len(inputs)):
            filter_parts.append(
                f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2[v{i}]"
            )

        if len(inputs) > 1:
            # Concatenação simples
            concat_inputs = "".join([f"[v{i}]" for i in range(len(inputs))])
            filter_parts.append(f"{concat_inputs}concat=n={len(inputs)}:v=1:a=0[vout]")
            final_output = "[vout]"
        else:
            final_output = "[v0]"

        cmd.extend(["-filter_complex", ";".join(filter_parts)])
        cmd.extend(["-map", final_output])

        # Configurações de codec
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

        return cmd

    def _add_audio_to_video_legacy(
        self,
        video_path: Path,
        timeline: Timeline,
        output_path: Path,
        settings: RenderSettings,
    ):
        """Adiciona áudio ao vídeo com suporte a logo, overlays e capa"""

        audio_tracks = timeline.audio
        if not audio_tracks:
            # Sem áudio, apenas copiar vídeo
            import shutil

            shutil.copy2(video_path, output_path)
            return

        self.logger.info("Adicionando áudio ao vídeo")

        # Calcular duração baseada apenas na narração (primeiro áudio)
        narration_duration = 0.0
        if audio_tracks and audio_tracks[0].clips:
            # Usar apenas o primeiro clip de áudio (narração)
            first_clip = audio_tracks[0].clips[0]
            narration_duration = (first_clip.out_ms - first_clip.in_ms) / 1000.0

        if narration_duration == 0:
            # Fallback: usar duração do vídeo temporário
            narration_duration = (
                self._get_video_duration_legacy(Path(video_path)) or 120.0
            )

        cmd = [str(ffmpeg_bin()), "-y", "-i", str(video_path)]

        # Adicionar inputs de áudio
        audio_inputs = []
        for track in audio_tracks:
            for clip in track.clips:
                cmd.extend(["-i", str(clip.media_path)])
                audio_inputs.append(
                    len(audio_inputs) + 1
                )  # Índice do input (0 é vídeo)

        # Coletar todos os efeitos visuais do primeiro clip
        video_track = timeline.video[0] if timeline.video else None
        visual_effects = []

        if video_track and video_track.clips:
            for effect in video_track.clips[0].effects:  # Apenas primeiro clip
                if effect.name in ["logo", "overlay", "cover", "overlay_chromakey"]:
                    visual_effects.append(effect)
                    self.logger.info(
                        f"[DEBUG] Efeito visual encontrado: {effect.name} com params: {effect.params}"
                    )

        # Adicionar inputs para efeitos visuais
        input_counter = len(audio_inputs) + 1
        effect_inputs = {}

        for effect in visual_effects:
            effect_path = effect.params.get("path")
            if effect_path and Path(effect_path).exists():
                if effect.name == "overlay":
                    # Para overlay de vídeo, calcular quantos loops são necessários baseado na narração
                    overlay_duration = self._get_video_duration_legacy(
                        Path(effect_path)
                    )
                    if overlay_duration and narration_duration:
                        loops_needed = max(
                            1, int((narration_duration / overlay_duration) + 1)
                        )
                        self.logger.info(
                            f"Overlay: {overlay_duration}s, Narração: {narration_duration}s, Loops: {loops_needed}"
                        )
                        cmd.extend(
                            ["-stream_loop", str(loops_needed), "-i", str(effect_path)]
                        )
                    else:
                        self.logger.warning(
                            f"Não foi possível calcular duração, usando 8 loops"
                        )
                        cmd.extend(["-stream_loop", "8", "-i", str(effect_path)])
                    effect_inputs[effect.name] = input_counter
                    input_counter += 1
                elif effect.name == "overlay_chromakey":
                    # Overlay de vídeo chromakey: adicionar input normalmente
                    cmd.extend(["-i", str(effect_path)])
                    # Armazenar todos os overlays chromakey (pode haver vários)
                    if "overlay_chromakey" not in effect_inputs:
                        effect_inputs["overlay_chromakey"] = []
                    effect_inputs["overlay_chromakey"].append((input_counter, effect))
                    input_counter += 1
                else:
                    # Para logo e capa (imagens), adicionar normalmente
                    cmd.extend(["-i", str(effect_path)])
                    effect_inputs[effect.name] = input_counter
                    input_counter += 1

        # Construir filtros separadamente
        filter_parts = []
        current_video = "[0:v]"

        # Aplicar efeitos visuais em ordem: overlay -> logo -> capa
        for effect in visual_effects:
            if effect.name == "overlay" and effect.name in effect_inputs:
                input_idx = effect_inputs[effect.name]
                overlay_input = f"[{input_idx}:v]"
                overlay_effect = OverlayEffect(effect.params)
                input_label = current_video.strip("[]")
                overlay_label = overlay_input.strip("[]")
                output_label = "overlay_out"
                filter_snippet = overlay_effect.build_filter(
                    input_label, overlay_label, output_label
                )
                filter_parts.append(filter_snippet)
                current_video = f"[{output_label}]"
            elif effect.name == "logo" and effect.name in effect_inputs:
                input_idx = effect_inputs[effect.name]
                logo_input = f"[{input_idx}:v]"
                logo_effect = LogoEffect(effect.params)
                input_label = current_video.strip("[]")
                logo_label = logo_input.strip("[]")
                output_label = "logo_out"
                filter_snippet = logo_effect.build_filter(
                    input_label, logo_label, output_label
                )
                filter_parts.append(filter_snippet)
                current_video = f"[{output_label}]"
            elif effect.name == "cover" and effect.name in effect_inputs:
                input_idx = effect_inputs[effect.name]
                cover_input = f"[{input_idx}:v]"
                cover_effect = CoverEffect(effect.params)
                input_label = current_video.strip("[]")
                cover_label = cover_input.strip("[]")
                output_label = "cover_out"
                filter_snippet = cover_effect.build_filter(
                    input_label, cover_label, output_label
                )
                filter_parts.append(filter_snippet)
                current_video = f"[{output_label}]"

        # Integrar chroma overlays do config.json
        import json
        from app.infra.media_io import has_audio_stream

        config_path = Path(__file__).parents[2] / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            chromas = config_data.get("chromas", [])
            for idx, chroma in enumerate(chromas):
                chroma_effect = ChromaOverlayEffect(chroma)
                chroma_path = chroma.get("path")
                if chroma_path:
                    cmd.extend(["-i", str(chroma_path)])
                    chroma_video_label = f"{current_video.strip('[]')}"
                    chroma_overlay_label = f"{input_counter}:v"
                    v_out = f"chroma_v{idx}"
                    a_out = f"chroma_a{idx}"
                    # Sempre remover o áudio do chroma overlay: nunca adicionar [N:a] do chroma
                    filter_snippet = chroma_effect.build_filter(
                        chroma_video_label,
                        chroma_overlay_label,
                        None,
                        None,
                        v_out,
                        None,
                    )
                    filter_parts.append(filter_snippet)
                    current_video = f"[{v_out}]"
                    input_counter += 1

        # Se há filtros visuais, definir saída de vídeo
        if filter_parts:
            video_output = current_video
        else:
            video_output = "0:v"

        # Filtro de áudio (mix)
        chroma_audio_output = None
        chroma_present = False
        # Detectar se algum filter_parts contém chroma_a (áudio do chroma)
        for part in filter_parts:
            if "chroma_a" in part:
                chroma_present = True
                # Pega o último label de chroma_a gerado
                import re

                m = re.findall(r"\[chroma_a(\d+)\]", part)
                if m:
                    chroma_audio_output = f"[chroma_a{m[-1]}]"
                else:
                    chroma_audio_output = "[chroma_a0]"
        if not chroma_present:
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
            else:
                audio_output = None

        # Aplicar filtros se necessário
        if filter_parts:
            cmd.extend(["-filter_complex", ";".join(filter_parts)])
            cmd.extend(["-map", video_output])
            if chroma_present and chroma_audio_output:
                cmd.extend(["-map", chroma_audio_output])
            elif not chroma_present and audio_output:
                cmd.extend(["-map", audio_output])
        else:
            # Sem filtros, mapear diretamente
            cmd.extend(["-map", "0:v"])
            if audio_inputs:
                cmd.extend(["-map", f"{audio_inputs[0]}:a"])

        # Configurações finais
        cmd.extend(
            [
                "-c:v",
                "libx264" if filter_parts else "copy",  # Recodificar se há filtros
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-t",
                str(narration_duration),  # Cortar na duração da narração
                str(output_path),
            ]
        )

        # Executar usando Runner
        try:
            self.runner.run(cmd, timeout=180)  # 3 minutos para overlays
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Erro FFmpeg: {e.stderr}")
            raise RuntimeError(f"FFmpeg falhou: {e.stderr}")
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Timeout após 180s: {' '.join(map(str, cmd))}")
            raise RuntimeError(f"Comando FFmpeg excedeu timeout de 180s")

    def _get_video_duration_legacy(self, video_path: Path) -> Optional[float]:
        """
        Método legacy - TODO: migrar para GraphBuilder + CliBuilder + Runner
        Obtém a duração de um arquivo de vídeo em segundos
        """
        try:
            cmd = [
                str(ffmpeg_bin()),
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(video_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                try:
                    duration = float(result.stdout.strip())
                    self.logger.info(f"Duração de {video_path.name}: {duration}s")
                    return duration
                except ValueError:
                    pass

            # Fallback usando ffprobe
            cmd = [
                str(ffmpeg_bin()).replace("ffmpeg.exe", "ffprobe.exe"),
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(video_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                self.logger.info(f"Duração de {video_path.name} (ffprobe): {duration}s")
                return duration

            return None

        except Exception as e:
            self.logger.warning(f"Não foi possível obter duração de {video_path}: {e}")
            return None

    # TODO: Próxima etapa de migração
    # - Converter _add_audio_to_video_legacy para usar GraphBuilder
    # - Converter _get_video_duration_legacy para usar Runner
    # - Remover todos os métodos legacy após migração completa
    #
    # A arquitetura final será:
    # render() -> GraphBuilder.build() -> CliBuilder.build_command() -> Runner.run()
    # Isso separará completamente as responsabilidades seguindo Clean Architecture
