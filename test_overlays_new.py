#!/usr/bin/env python3
"""
Teste da nova arquitetura com overlays e transições.
"""

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.append(str(Path(__file__).parent))

from app.application.services.video_creation_service import (
    VideoCreationService,
    VideoCreationRequest,
)


def main():
    print("=== Teste com Overlays e Transições ===")

    # Usar apenas 5 imagens para teste com overlays
    image_paths = [
        Path("arquivos_teste/1/1.png"),
        Path("arquivos_teste/1/2.png"),
        Path("arquivos_teste/1/3.png"),
        Path("arquivos_teste/1/4.png"),
        Path("arquivos_teste/1/5.png"),
    ]

    # Verificar se os arquivos existem
    for img in image_paths:
        if not img.exists():
            print(f"❌ Arquivo não encontrado: {img}")
            return 1

    audio_path = Path("arquivos_teste/narracao2.mp3")
    music_path = Path("arquivos_teste/fundo.mp3")
    logo_path = Path("arquivos_teste/logo.png")

    for path in [audio_path, music_path, logo_path]:
        if not path.exists():
            print(f"❌ Arquivo não encontrado: {path}")
            return 1

    output_path = Path("output_videos/video_test_overlays_new.mp4")

    # Criar request com overlays
    request = VideoCreationRequest(
        images=image_paths,
        audio_path=audio_path,
        output_path=output_path,
        segment_duration=4.0,  # 4 segundos por imagem
        background_music_path=music_path,
        background_music_volume=0.2,
        logo_path=logo_path,
        logo_position="top_right",
        logo_opacity=0.8,
        logo_scale=0.15,
        transition="fade",  # Tentar com transição
        encoder="h264_nvenc",
    )

    # Criar serviço principal
    service = VideoCreationService()

    try:
        print(
            f"🎬 Criando vídeo com {len(image_paths)} imagens, música de fundo e logo..."
        )
        print(f"📁 Saída: {output_path}")

        result_path = service.create_video(request)

        if result_path.exists():
            size_mb = result_path.stat().st_size / 1024 / 1024
            print(f"✅ Vídeo criado com sucesso: {result_path}")
            print(f"📏 Tamanho: {size_mb:.2f} MB")
            return 0
        else:
            print("❌ Falha na criação do vídeo")
            return 1

    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
