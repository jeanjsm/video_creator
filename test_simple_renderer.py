#!/usr/bin/env python3
"""
Teste da nova arquitetura com renderizador simples.
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
    print("=== Teste com Renderizador Simples ===")

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

    if not audio_path.exists():
        print(f"❌ Arquivo não encontrado: {audio_path}")
        return 1

    output_path = Path("output_videos/video_test_simple_renderer.mp4")

    # Criar request simples
    request = VideoCreationRequest(
        images=image_paths,
        audio_path=audio_path,
        output_path=output_path,
        segment_duration=3.0,  # 3 segundos por imagem
        encoder="libx264",  # Usar codec estável
    )

    # Criar serviço principal
    service = VideoCreationService()

    try:
        print(f"🎬 Criando vídeo com {len(image_paths)} imagens...")
        print(f"📁 Saída: {output_path}")
        print("⏱️  Aguarde cerca de 30-60 segundos...")

        start_time = __import__("time").time()
        result_path = service.create_video(request)
        end_time = __import__("time").time()

        if result_path.exists():
            size_mb = result_path.stat().st_size / 1024 / 1024
            duration = end_time - start_time
            print(f"✅ Vídeo criado com sucesso em {duration:.1f}s: {result_path}")
            print(f"📏 Tamanho: {size_mb:.2f} MB")

            # Testar com ffprobe
            from app.infra.paths import ffprobe_bin
            import subprocess

            try:
                probe_cmd = [
                    str(ffprobe_bin()),
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(result_path),
                ]
                probe_result = subprocess.run(
                    probe_cmd, capture_output=True, text=True, timeout=10
                )
                if probe_result.returncode == 0:
                    print("✅ Arquivo de vídeo válido")
                else:
                    print("⚠️  Possível problema no arquivo de vídeo")
            except:
                print("⚠️  Não foi possível verificar o arquivo")

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
