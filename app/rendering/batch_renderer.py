# -*- coding: utf-8 -*-
"""
Renderizador em lotes para evitar sobrecarga de comandos FFmpeg complexos
"""

from pathlib import Path
from typing import List, Optional
import tempfile
import os

from ..domain.models.timeline import Timeline, Track, Clip, RenderSettings
from .graph_builder import GraphBuilder
from .cli_builder import CliBuilder
from .runner import Runner
from ..infra.logging import get_logger
from ..infra.paths import ffmpeg_bin


class BatchRenderer:
    """Renderiza vídeos em lotes menores para evitar complexidade excessiva"""

    def __init__(self, max_inputs_per_batch: int = 10):
        self.max_inputs_per_batch = max_inputs_per_batch
        self.logger = get_logger("BatchRenderer")
        self.graph_builder = GraphBuilder()
        self.cli_builder = CliBuilder()
        self.runner = Runner()

    def render(
        self, timeline: Timeline, settings: RenderSettings, output_path: Path
    ) -> Path:
        """Renderiza timeline dividindo em lotes se necessário"""

        # Verifica se precisa dividir em lotes
        video_track = timeline.video[0] if timeline.video else None
        if not video_track or len(video_track.clips) <= self.max_inputs_per_batch:
            # Renderização direta
            return self._render_direct(timeline, settings, output_path)

        # Renderização em lotes
        self.logger.info(
            f"Timeline com {len(video_track.clips)} clips, dividindo em lotes de {self.max_inputs_per_batch}"
        )
        return self._render_batched(timeline, settings, output_path)

    def _render_direct(
        self, timeline: Timeline, settings: RenderSettings, output_path: Path
    ) -> Path:
        """Renderização direta sem divisão em lotes"""
        self.logger.info("Renderização direta sem lotes")

        graph = self.graph_builder.build(timeline, settings)
        cmd = self.cli_builder.make_command(graph, output_path, settings)

        result = self.runner.run(cmd, timeout=600)  # 10 minutos

        if result.returncode == 0:
            self.logger.info(f"Renderização concluída: {output_path}")
            return output_path
        else:
            raise RuntimeError(f"Erro na renderização: {result.stderr}")

    def _render_batched(
        self, timeline: Timeline, settings: RenderSettings, output_path: Path
    ) -> Path:
        """Renderização dividida em lotes"""
        video_track = timeline.video[0]
        clips = video_track.clips

        # Dividir clips em lotes
        batches = [
            clips[i : i + self.max_inputs_per_batch]
            for i in range(0, len(clips), self.max_inputs_per_batch)
        ]

        batch_videos = []

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Renderizar cada lote
                for i, batch_clips in enumerate(batches):
                    self.logger.info(
                        f"Renderizando lote {i+1}/{len(batches)} com {len(batch_clips)} clips"
                    )

                    # Criar timeline temporária para o lote
                    batch_track = Track(
                        id=f"batch_{i}", kind="video", clips=batch_clips
                    )

                    # Ajustar timing dos clips do lote
                    adjusted_clips = []
                    current_start = 0

                    for clip in batch_clips:
                        duration = clip.out_ms - clip.in_ms
                        adjusted_clip = Clip(
                            id=clip.id,
                            media_path=clip.media_path,
                            in_ms=clip.in_ms,
                            out_ms=clip.out_ms,
                            start_ms=current_start,
                            effects=clip.effects,
                        )
                        adjusted_clips.append(adjusted_clip)
                        current_start += duration

                    batch_track = Track(
                        id=f"batch_{i}", kind="video", clips=adjusted_clips
                    )

                    batch_timeline = Timeline(
                        fps=timeline.fps,
                        resolution=timeline.resolution,
                        video=[batch_track],
                        audio=[],  # Sem áudio nos lotes individuais
                    )

                    # Renderizar lote
                    batch_output = temp_path / f"batch_{i}.mp4"
                    self._render_direct(batch_timeline, settings, batch_output)
                    batch_videos.append(batch_output)

                # Concatenar todos os lotes + áudio
                self.logger.info(f"Concatenando {len(batch_videos)} lotes")
                self._concatenate_batches(
                    batch_videos, timeline.audio, output_path, settings
                )

                return output_path

        except Exception as e:
            self.logger.error(f"Erro na renderização em lotes: {e}")
            raise
        finally:
            # Cleanup dos arquivos temporários
            for batch_video in batch_videos:
                if batch_video.exists():
                    try:
                        batch_video.unlink()
                    except:
                        pass

    def _concatenate_batches(
        self,
        batch_videos: List[Path],
        audio_tracks: List[Track],
        output_path: Path,
        settings: RenderSettings,
    ):
        """Concatena os lotes renderizados e adiciona áudio"""

        # Criar arquivo de lista para concatenação
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for batch_video in batch_videos:
                f.write(f"file '{batch_video.absolute()}'\n")
            concat_file = Path(f.name)

        try:
            # Comando de concatenação
            cmd = [
                str(ffmpeg_bin()),
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
            ]

            # Adicionar áudio se houver
            if audio_tracks:
                for track in audio_tracks:
                    for clip in track.clips:
                        cmd.extend(["-i", str(clip.media_path)])

                # Mapear streams
                cmd.extend(["-map", "0:v"])  # Vídeo concatenado
                if audio_tracks:
                    cmd.extend(["-map", "1:a"])  # Primeiro áudio

                # Filtro de áudio se necessário (volume, mix, etc)
                if len(audio_tracks) > 1 or any(
                    track.clips for track in audio_tracks if len(track.clips) > 1
                ):
                    audio_filter = self._build_audio_filter(audio_tracks)
                    if audio_filter:
                        cmd.extend(["-filter_complex", audio_filter])
                        cmd.extend(["-map", "[aout]"])

            # Configurações de codec
            cmd.extend(
                [
                    "-c:v",
                    "libx264",  # Usar codec padrão
                    "-preset",
                    "medium",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-movflags",
                    "+faststart",
                    "-y",  # Sobrescrever
                    str(output_path),
                ]
            )

            result = self.runner.run(cmd, timeout=300)  # 5 minutos para concatenação

            if result.returncode != 0:
                raise RuntimeError(f"Erro na concatenação: {result.stderr}")

        finally:
            # Cleanup
            if concat_file.exists():
                concat_file.unlink()

    def _build_audio_filter(self, audio_tracks: List[Track]) -> Optional[str]:
        """Constrói filtro de áudio para múltiplas faixas"""
        if not audio_tracks:
            return None

        # Implementação simples - pode ser expandida
        filters = []
        input_idx = 1  # Começa em 1 porque 0 é o vídeo

        for track in audio_tracks:
            for clip in track.clips:
                filters.append(f"[{input_idx}:a]volume=1.0[a{input_idx}]")
                input_idx += 1

        if len(filters) > 1:
            # Mix de múltiplos áudios
            inputs = "".join([f"[a{i}]" for i in range(1, input_idx)])
            filters.append(f"{inputs}amix=inputs={input_idx-1}:duration=first[aout]")
        else:
            # Apenas renomear a saída
            filters.append("[a1]anull[aout]")

        return ";".join(filters)
