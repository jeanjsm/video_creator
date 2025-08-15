
"""
main.py — Interface/Adapter (Clean Architecture)
------------------------------------------------
Responsável por orquestrar a aplicação, ler argumentos, injetar dependências e chamar o core.
Não contém lógica de negócio, apenas orquestração e interface (CLI).
"""


import argparse
import os
from infra.config import get_config
from video_creator.core import criar_video

def main():
    parser = argparse.ArgumentParser(description="Cria um vídeo a partir de uma narração e imagens usando FFmpeg.")
    parser.add_argument('--audio', required=True, help='Arquivo de áudio da narração (ex: narracao.mp3)')
    # Não exige mais o argumento --imagens
    parser.add_argument('--transicao', choices=['fade', 'smoothleft', 'circleopen', 'none'], default='none', help="Tipo de transição entre imagens: 'fade' (padrão), 'zoom', 'simplezoom' ou 'none' (sem transição)")
    parser.add_argument('--efeito', choices=['fade', 'zoom', 'pendulo', 'simplezoom', 'none'], default='none', help="Efeito visual nas imagens: 'fade' (padrão), 'zoom', 'pendulo', 'simplezoom' ou 'none' (sem efeito)")
    parser.add_argument('--encoder', choices=['libx264', 'h264_nvenc'], default='libx264', help="Encoder de vídeo: 'libx264' (CPU, padrão) ou 'h264_nvenc' (GPU NVIDIA)")
    parser.add_argument('--saida', required=True, help='Arquivo de saída do vídeo (ex: video.mp4)')
    args = parser.parse_args()

    # Lê configurações do arquivo config.json via camada infra
    config = get_config()
    segment_duration = config.get('segment_duration', 3)
    pasta_imagens = config.get('image_source_dir', '')
    ffmpeg_path = os.path.abspath(config.get('ffmpeg_path', os.path.join(os.path.dirname(__file__), '_internal', 'ffmpeg', 'bin', 'ffmpeg.exe')))
    ffprobe_path = os.path.abspath(config.get('ffprobe_path', os.path.join(os.path.dirname(__file__), '_internal', 'ffmpeg', 'bin', 'ffprobe.exe')))

    # Busca todas as imagens da pasta configurada
    if pasta_imagens:
        exts = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
        imagens = [os.path.join(pasta_imagens, f) for f in sorted(os.listdir(pasta_imagens)) if f.lower().endswith(exts)]
        if not imagens:
            print(f"Nenhuma imagem encontrada em {pasta_imagens}")
            return
    else:
        print("Pasta de imagens não configurada no config.json.")
        return

    transicao_tipo = args.transicao if args.transicao != 'none' else None
    criar_video(
        args.audio,
        imagens,
        args.saida,
        segment_duration=segment_duration,
        transicao=transicao_tipo,
        efeito=args.efeito,
        encoder=args.encoder,
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path
    )

if __name__ == "__main__":
    main()
