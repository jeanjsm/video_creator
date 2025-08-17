#!/usr/bin/env python3
"""
Teste simples da nova arquitetura com apenas algumas imagens.
"""

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.append(str(Path(__file__).parent))

from app.application.services.video_creation_service import (
    VideoCreationService,
    VideoCreationRequest,
)
from app.rendering.graph_builder import GraphBuilder
from app.rendering.cli_builder import CliBuilder
from app.rendering.runner import Runner
from app.infra.media_io import MediaIO
from app.infra.paths import ffmpeg_bin


def main():
    print("=== Teste Simples da Nova Arquitetura ===")

    # Usar apenas 3 imagens para teste simples
    image_paths = [
        Path("arquivos_teste/1/1.png"),
        Path("arquivos_teste/1/2.png"),
        Path("arquivos_teste/1/3.png"),
    ]

    # Verificar se os arquivos existem
    for img in image_paths:
        if not img.exists():
            print(f"❌ Arquivo não encontrado: {img}")
            return 1

    audio_path = Path("arquivos_teste/narracao2.mp3")
    if not audio_path.exists():
        print(f"❌ Arquivo de áudio não encontrado: {audio_path}")
        return 1

    output_path = Path("output_videos/video_test_simple.mp4")

    # Criar request
    request = VideoCreationRequest(
        images=image_paths,
        audio_path=audio_path,
        output_path=output_path,
        segment_duration=5.0,  # 5 segundos por imagem para teste
        background_music_path=None,
        background_music_volume=0.2,
    )

    # Criar serviço principal
    service = VideoCreationService()

    try:
        print(f"🎬 Criando vídeo com {len(image_paths)} imagens...")
        print(f"📁 Saída: {output_path}")

        service.create_video(request)

        if output_path.exists():
            print(f"✅ Vídeo criado com sucesso: {output_path}")
            print(f"📏 Tamanho: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
            return 0
        else:
            print("❌ Falha na criação do vídeo")
            return 1

    except Exception as e:
        print(f"❌ Erro: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
