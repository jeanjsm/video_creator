# -*- coding: utf-8 -*-
"""
Execução de comandos FFmpeg com progresso
"""


import subprocess
import re
import threading
import queue
from dataclasses import dataclass
from typing import Callable, Optional
from pathlib import Path
from app.infra.logging import get_logger


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
        self,
        cmd: list[str],
        on_progress: Callable[[Progress], None] = None,
        timeout: Optional[float] = 300,  # 5 minutos por padrão
    ) -> subprocess.CompletedProcess:
        """Executa comando FFmpeg com callback de progresso e timeout"""
        logger = get_logger("Runner")
        logger.info("Executando comando FFmpeg: %s", " ".join(map(str, cmd)))

        # Para Windows, simplificar execução para evitar travamentos
        import os
        import time

        # Adiciona parâmetros para progresso se callback fornecido E não for Windows
        if on_progress and os.name != "nt":
            cmd_with_progress = cmd + ["-progress", "pipe:1"]
        else:
            cmd_with_progress = cmd
            if on_progress and os.name == "nt":
                logger.warning(
                    "Progresso desabilitado no Windows para evitar travamentos"
                )

        # Configurações específicas para Windows
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            # Usar execução simples no Windows para evitar travamentos
            if os.name == "nt" or not on_progress:
                result = subprocess.run(
                    cmd_with_progress,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    **kwargs,
                )

                if result.returncode == 0:
                    logger.info("Comando FFmpeg finalizado com sucesso.")
                else:
                    logger.error(
                        "Comando FFmpeg retornou código %d. Stderr: %s",
                        result.returncode,
                        result.stderr,
                    )
                    raise subprocess.CalledProcessError(
                        result.returncode, cmd, result.stdout, result.stderr
                    )

                return result

            # Usar versão com progresso apenas no Linux/macOS
            process = subprocess.Popen(
                cmd_with_progress,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True,
                **kwargs,
            )

            stdout_lines = []
            stderr_lines = []
            start_time = time.time()

            # Versão simplificada para Linux/macOS com progresso
            while True:
                # Verifica timeout
                if timeout and (time.time() - start_time) > timeout:
                    logger.error(f"Timeout de {timeout}s excedido, terminando processo")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.error("Processo não terminou graciosamente, forçando...")
                        process.kill()
                        process.wait()
                    raise subprocess.TimeoutExpired(cmd_with_progress, timeout)

                output = process.stdout.readline() if process.stdout else ""
                if output == "" and process.poll() is not None:
                    break

                if output and on_progress:
                    progress = self._parse_progress_line(output.strip())
                    if progress:
                        on_progress(progress)

                if output:
                    stdout_lines.append(output.strip())

            # Captura stderr
            if process.stderr:
                stderr_lines = process.stderr.readlines()

            return_code = process.poll()

            if return_code == 0:
                logger.info("Comando FFmpeg finalizado com sucesso.")
            else:
                logger.error(
                    "Comando FFmpeg retornou código %d. Stderr: %s",
                    return_code,
                    " ".join(stderr_lines),
                )
                raise subprocess.CalledProcessError(
                    return_code, cmd, "\n".join(stdout_lines), "\n".join(stderr_lines)
                )

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=return_code,
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
            )

        except subprocess.TimeoutExpired as e:
            logger.error(f"Timeout após {timeout}s: {' '.join(map(str, cmd))}")
            raise RuntimeError(f"Comando FFmpeg excedeu timeout de {timeout}s")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg falhou com código {e.returncode}: {e.stderr}")
            raise RuntimeError(f"FFmpeg falhou: {e.stderr}")
        except Exception as e:
            logger.error(f"Erro inesperado: {e}")
            raise RuntimeError(f"Erro na execução do FFmpeg: {e}")

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

    def run_image_conversion(
        self, cmd: list[str], timeout: Optional[float] = 30
    ) -> subprocess.CompletedProcess:
        """Executa conversão de imagem para vídeo com timeout reduzido"""
        logger = get_logger("Runner")
        logger.info("Executando conversão de imagem para vídeo")
        # Para conversões de imagem, desabilitar progresso para evitar travamentos
        return self.run(cmd, on_progress=None, timeout=timeout)

    def run_concat(
        self, cmd: list[str], timeout: Optional[float] = 120
    ) -> subprocess.CompletedProcess:
        """Executa concatenação de vídeos"""
        logger = get_logger("Runner")
        logger.info("Executando concatenação de vídeos")
        return self.run(cmd, timeout=timeout)

    def run_audio_mix(
        self, cmd: list[str], timeout: Optional[float] = 180
    ) -> subprocess.CompletedProcess:
        """Executa mixagem de áudio"""
        logger = get_logger("Runner")
        logger.info("Executando mixagem de áudio")
        return self.run(cmd, timeout=timeout)
