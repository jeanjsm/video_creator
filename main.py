"""
main.py — Interface/Adapter (Clean Architecture)
------------------------------------------------
Responsável por orquestrar a aplicação, ler argumentos, injetar dependências e chamar o core.
Não contém lógica de negócio, apenas orquestração e interface (CLI).
"""

import argparse
import os
import logging
from app.infra.config import get_config
from app.application.services.core import criar_video


def main():
    # Configura logging para arquivo
    logging.basicConfig(
        filename="debug_video_creator.log",
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Cria um vídeo a partir de uma narração e imagens usando FFmpeg."
    )
    # Overlay com chroma key (fundo verde)
    import json

    # parser.add_argument('--overlay_chromas', help='JSON string ou arquivo JSON com lista de overlays chroma. Exemplo: [{"path": "efeito.mp4", "start": 2, "opacidade": 1, "tolerancia": 0.2}]')
    # Capa (cover)
    parser.add_argument(
        "--capa", help="Arquivo de imagem para capa (cover) sobre o vídeo"
    )
    parser.add_argument(
        "--capa_opacidade",
        type=float,
        default=1.0,
        help="Opacidade da capa (0.0 a 1.0, padrão=1.0)",
    )
    parser.add_argument(
        "--capa_tamanho",
        type=float,
        default=1.0,
        help="Tamanho relativo da capa (0.0 a 1.0, padrão=1.0)",
    )
    parser.add_argument(
        "--capa_posicao",
        choices=["centro", "top_left", "top_right", "bottom_left", "bottom_right"],
        default="centro",
        help="Posição da capa (padrão: centro)",
    )
    parser.add_argument(
        "--audio", required=True, help="Arquivo de áudio da narração (ex: narracao.mp3)"
    )
    parser.add_argument("--musica_fundo", help="Arquivo de música de fundo (opcional)")
    parser.add_argument(
        "--volume_musica",
        type=float,
        default=0.2,
        help="Volume da música de fundo (0.0 a 1.0, padrão=0.2)",
    )
    parser.add_argument("--logo", help="Arquivo da logo (opcional)")
    parser.add_argument(
        "--logo_posicao",
        choices=["top_left", "top_right", "bottom_left", "bottom_right"],
        default="top_right",
        help="Posição da logo (padrão: top_left)",
    )
    parser.add_argument(
        "--logo_opacidade",
        type=float,
        default=1.0,
        help="Opacidade da logo (0.0 a 1.0, padrão=1.0)",
    )
    parser.add_argument(
        "--logo_tamanho",
        type=float,
        default=0.15,
        help="Tamanho relativo da logo (0.0 a 1.0, padrão=0.15)",
    )
    parser.add_argument(
        "--transicao",
        choices=["fade", "smoothleft", "circleopen", "none"],
        default="none",
        help="Tipo de transição entre imagens: 'fade' (padrão), 'zoom', 'simplezoom' ou 'none' (sem transição)",
    )
    parser.add_argument(
        "--efeito",
        choices=["fade", "zoom", "pendulo", "simplezoom", "none"],
        default="none",
        help="Efeito visual nas imagens: 'fade' (padrão), 'zoom', 'pendulo', 'simplezoom' ou 'none' (sem efeito)",
    )
    parser.add_argument(
        "--encoder",
        choices=["libx264", "h264_nvenc"],
        default="libx264",
        help="Encoder de vídeo: 'libx264' (CPU, padrão) ou 'h264_nvenc' (GPU NVIDIA)",
    )
    parser.add_argument(
        "--saida", required=True, help="Arquivo de saída do vídeo (ex: video.mp4)"
    )
    # Overlays
    parser.add_argument(
        "--overlay1", help="Arquivo de overlay 1 (imagem ou vídeo, opcional)"
    )
    parser.add_argument(
        "--overlay1_opacidade",
        type=float,
        default=0.4,
        help="Opacidade do overlay 1 (0.0 a 1.0, padrão=1.0)",
    )
    parser.add_argument(
        "--overlay2", help="Arquivo de overlay 2 (imagem ou vídeo, opcional)"
    )
    parser.add_argument(
        "--overlay2_opacidade",
        type=float,
        default=0.4,
        help="Opacidade do overlay 2 (0.0 a 1.0, padrão=1.0)",
    )
    args = parser.parse_args()
    logging.debug(f"[DEBUG main.py] args: {vars(args)}")

    # Lê configurações do arquivo config.json via camada infra
    config = get_config()
    segment_duration = config.get("segment_duration", 3)
    pasta_imagens = config.get("image_source_dir", "")
    ffmpeg_path = os.path.abspath(
        config.get(
            "ffmpeg_path",
            os.path.join(
                os.path.dirname(__file__), "_internal", "ffmpeg", "bin", "ffmpeg.exe"
            ),
        )
    )
    ffprobe_path = os.path.abspath(
        config.get(
            "ffprobe_path",
            os.path.join(
                os.path.dirname(__file__), "_internal", "ffmpeg", "bin", "ffprobe.exe"
            ),
        )
    )

    # Busca todas as imagens da pasta configurada
    if pasta_imagens:
        exts = (".jpg", ".jpeg", ".png", ".bmp", ".gif")
        imagens = [
            os.path.join(pasta_imagens, f)
            for f in sorted(os.listdir(pasta_imagens))
            if f.lower().endswith(exts)
        ]
        if not imagens:
            print(f"Nenhuma imagem encontrada em {pasta_imagens}")
            return
    else:
        print("Pasta de imagens não configurada no config.json.")
        return

    transicao_tipo = args.transicao if args.transicao != "none" else None
    overlays = []
    if args.overlay1:
        overlays.append({"path": args.overlay1, "opacidade": args.overlay1_opacidade})
    if args.overlay2:
        overlays.append({"path": args.overlay2, "opacidade": args.overlay2_opacidade})

    # Lê overlay_chromas do config.json
    # overlay_chromas lido do config.json, mas não utilizado

    # Normaliza capa_posicao para evitar problemas de case ou espaços
    capa_posicao = args.capa_posicao.strip().lower() if args.capa_posicao else "centro"
    criar_video(
        args.audio,
        imagens,
        args.saida,
        segment_duration=segment_duration,
        transicao=transicao_tipo,
        efeito=args.efeito,
        encoder=args.encoder,
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        background_music_path=args.musica_fundo,
        background_music_volume=args.volume_musica,
        logo_path=args.logo,
        logo_pos=args.logo_posicao,
        logo_opacity=args.logo_opacidade,
        logo_scale=args.logo_tamanho,
        overlays=overlays,
        capa=args.capa,
        capa_opacidade=args.capa_opacidade,
        capa_tamanho=args.capa_tamanho,
        capa_posicao=capa_posicao,
        # overlay_chromas removido
    )


if __name__ == "__main__":
    main()
