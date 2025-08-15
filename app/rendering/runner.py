# -*- coding: utf-8 -*-
"""
Execução de comandos FFmpeg com progresso
"""

import subprocess
import re
from dataclasses import dataclass
from typing import Callable, Optional
from pathlib import Path


@dataclass(frozen=True)
class Progress:
    """Representa o progresso de renderização"""

    out_time_ms: int
    speed: Optional[float]
    percent: Optional[float]
    frame: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[str] = None


class Runner:
    """Executa comandos FFmpeg com monitoramento de progresso"""

    def run(
        self, cmd: list[str], on_progress: Callable[[Progress], None] = None
    ) -> subprocess.CompletedProcess:
        """Executa comando FFmpeg com callback de progresso"""

        # Adiciona parâmetros para progresso se callback fornecido
        if on_progress:
            cmd_with_progress = cmd + ["-progress", "pipe:1"]
        else:
            cmd_with_progress = cmd

        process = subprocess.Popen(
            cmd_with_progress,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True,
        )

        stdout_lines = []
        stderr_lines = []

        # Lê saída em tempo real
        while True:
            output = process.stdout.readline() if process.stdout else ""
            if output == "" and process.poll() is not None:
                break

            if output and on_progress:
                # Parseia linha de progresso
                progress = self._parse_progress_line(output.strip())
                if progress:
                    on_progress(progress)

            if output:
                stdout_lines.append(output.strip())

        # Captura stderr
        if process.stderr:
            stderr_lines = process.stderr.readlines()

        return_code = process.poll()

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=return_code,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
        )

    def _parse_progress_line(self, line: str) -> Optional[Progress]:
        """Parseia linha de progresso do FFmpeg"""
        if not line or "=" not in line:
            return None

        # FFmpeg progress format: key=value
        progress_data = {}
        for part in line.split():
            if "=" in part:
                key, value = part.split("=", 1)
                progress_data[key] = value

        if "out_time_ms" in progress_data:
            try:
                out_time_ms = int(progress_data["out_time_ms"])
                speed = (
                    float(progress_data.get("speed", "0").rstrip("x"))
                    if "speed" in progress_data
                    else None
                )
                frame = (
                    int(progress_data.get("frame", "0"))
                    if "frame" in progress_data
                    else None
                )
                fps = (
                    float(progress_data.get("fps", "0"))
                    if "fps" in progress_data
                    else None
                )

                return Progress(
                    out_time_ms=out_time_ms,
                    speed=speed,
                    percent=None,  # Seria calculado baseado na duração total
                    frame=frame,
                    fps=fps,
                    bitrate=progress_data.get("bitrate"),
                )
            except (ValueError, KeyError):
                pass

        return None
