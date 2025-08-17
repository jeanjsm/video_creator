#!/usr/bin/env python3
"""
Teste rápido para verificar efeitos visuais (logo, overlay, capa)
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
    print("=== Teste de Efeitos Visuais ===")

    # Usar apenas 3 imagens para teste rápido
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
    music_path = Path("arquivos_teste/fundo.mp3")
    logo_path = Path("arquivos_teste/logo.png")
    overlay_path = Path("arquivos_teste/overlay.mp4")
    capa_path = Path("arquivos_teste/capa.png")

    for path in [audio_path, music_path, logo_path, overlay_path, capa_path]:
        if not path.exists():
            print(f"❌ Arquivo não encontrado: {path}")
            return 1

    output_path = Path("output_videos/test_visual_effects.mp4")

    # Criar request com todos os efeitos visuais
    request = VideoCreationRequest(
        images=image_paths,
        audio_path=audio_path,
        output_path=output_path,
        segment_duration=5.0,  # 5 segundos por imagem para ver melhor os efeitos
        background_music_path=music_path,
        background_music_volume=0.2,
        # Logo no canto superior direito
        logo_path=logo_path,
        logo_position="top_right",
        logo_opacity=0.8,
        logo_scale=0.15,
        # Overlay de vídeo
        overlays=[{"path": str(overlay_path), "opacidade": 1.0}],
        # Capa no canto inferior direito
        cover_path=capa_path,
        cover_position="bottom_right",
        cover_opacity=1.0,
        cover_size=0.3,
        transition="fade",
        encoder="libx264",  # Usar libx264 para compatibilidade
    )

    # Criar serviço principal
    service = VideoCreationService()

    try:
        print("🎬 Criando vídeo com:")
        print(f"  📸 {len(image_paths)} imagens")
        print(f"  🎵 Música de fundo")
        print(f"  📺 Logo (top_right)")
        print(f"  🎥 Overlay de vídeo (centro)")
        print(f"  🖼️ Capa (bottom_right)")
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
