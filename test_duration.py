#!/usr/bin/env python3
"""
Teste específico para verificar cálculo de duração
"""

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.append(str(Path(__file__).parent))

from app.rendering.simple_renderer import SimpleRenderer


def main():
    print("=== Teste de Cálculo de Duração ===")

    renderer = SimpleRenderer()

    # Testar duração do overlay
    overlay_path = Path("arquivos_teste/overlay.mp4")
    if overlay_path.exists():
        duration = renderer._get_video_duration(overlay_path)
        print(f"Duração do overlay: {duration}s")

    # Testar duração de um vídeo temporário que seria criado
    test_video = Path("output_videos/test_visual_effects.mp4")
    if test_video.exists():
        duration = renderer._get_video_duration(test_video)
        print(f"Duração do vídeo de teste: {duration}s")

        if duration:
            overlay_duration = 30.067  # Duração conhecida do overlay
            loops_needed = max(1, int((duration / overlay_duration) + 2))
            print(f"Loops necessários: {loops_needed}")
            print(f"Duração do overlay com loops: {loops_needed * overlay_duration}s")


if __name__ == "__main__":
    main()
