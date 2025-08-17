"""
main.py — Interface CLI seguindo Clean Architecture
"""

import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

from app.infra.config import get_config
from app.infra.logging import setup_logging
from app.application.services.video_creation_service import (
    VideoCreationService,
    VideoCreationRequest,
)


def parse_overlays(overlay_args: List[str]) -> List[Dict[str, Any]]:
    """Converte argumentos de overlay para lista de dicionários"""
    overlays = []
    for overlay_path in overlay_args:
        overlays.append({"path": overlay_path, "opacidade": 1.0})
    return overlays


def get_images_from_config() -> List[Path]:
    """Obtém lista de imagens da configuração"""
    config = get_config()
    pasta_imagens = config.get("image_source_dir", "./arquivos_teste/1")

    images = []
    pasta_path = Path(pasta_imagens)

    if pasta_path.exists():
        # Busca imagens em ordem numérica
        for i in range(1, 100):  # limite razoável
            for ext in [".png", ".jpg", ".jpeg"]:
                img_path = pasta_path / f"{i}{ext}"
                if img_path.exists():
                    images.append(img_path)
                    break

    return images


def main():
    parser = argparse.ArgumentParser(
        description="Cria um vídeo a partir de uma narração e imagens usando FFmpeg."
    )

    # Overlays de vídeo com chromakey (após parser criado)
    for i in range(1, 6):  # Suporte até 5 overlays
        parser.add_argument(
            f"--chroma_video{i}", help=f"Overlay de vídeo chromakey {i}"
        )
        parser.add_argument(
            f"--chroma_start{i}",
            type=float,
            default=0.0,
            help=f"Segundo de início do overlay chromakey {i}",
        )
        parser.add_argument(
            f"--chroma_pos{i}",
            choices=["center", "top_left", "top_right", "bottom_left", "bottom_right"],
            default="center",
            help=f"Posição do overlay chromakey {i}",
        )
        parser.add_argument(
            f"--chroma_key{i}",
            type=str,
            default="green",
            help=f"Cor do chromakey do overlay {i} (ex: green, blue, 0x00FF00)",
        )

    # Setup logging
    setup_logging("debug_video_creator.log", logging.DEBUG)

    # Argumentos principais
    parser.add_argument("--audio", required=True, help="Arquivo de áudio da narração")
    parser.add_argument("--saida", required=True, help="Arquivo de saída do vídeo")

    # Configurações de vídeo
    parser.add_argument(
        "--encoder",
        choices=["libx264", "h264_nvenc"],
        default="libx264",
        help="Encoder de vídeo (padrão: libx264)",
    )
    parser.add_argument(
        "--transicao",
        choices=["fade", "smoothleft", "circleopen", "zoomin", "none", "random"],
        default="none",
        help="Tipo de transição entre imagens (ou 'random' para aleatório)",
    )

    # Música de fundo
    parser.add_argument("--musica_fundo", help="Arquivo de música de fundo")
    parser.add_argument(
        "--volume_musica",
        type=float,
        default=0.2,
        help="Volume da música de fundo (0.0 a 1.0)",
    )

    # Logo
    parser.add_argument("--logo", help="Arquivo da logo")
    parser.add_argument(
        "--logo_posicao",
        choices=["top_left", "top_right", "bottom_left", "bottom_right"],
        default="top_left",
        help="Posição da logo",
    )
    parser.add_argument(
        "--logo_opacidade",
        type=float,
        default=1.0,
        help="Opacidade da logo (0.0 a 1.0)",
    )
    parser.add_argument(
        "--logo_tamanho",
        type=float,
        default=0.15,
        help="Tamanho relativo da logo (0.0 a 1.0)",
    )

    # Overlays
    parser.add_argument("--overlay1", help="Primeiro overlay de vídeo")
    parser.add_argument("--overlay2", help="Segundo overlay de vídeo")

    # Capa
    parser.add_argument("--capa", help="Arquivo de imagem para capa")
    parser.add_argument(
        "--capa_opacidade",
        type=float,
        default=1.0,
        help="Opacidade da capa (0.0 a 1.0)",
    )
    parser.add_argument(
        "--capa_tamanho",
        type=float,
        default=1.0,
        help="Tamanho relativo da capa (0.0 a 1.0)",
    )
    parser.add_argument(
        "--capa_posicao",
        choices=["center", "top_left", "top_right", "bottom_left", "bottom_right"],
        default="center",
        help="Posição da capa",
    )

    # Argumentos extras para opacidade dos overlays (devem vir antes do parse_args)
    parser.add_argument(
        "--overlay1_opacidade",
        type=float,
        default=0.4,
        help="Opacidade do overlay1 (0.0 a 1.0)",
    )
    parser.add_argument(
        "--overlay2_opacidade",
        type=float,
        default=0.4,
        help="Opacidade do overlay2 (0.0 a 1.0)",
    )

    args = parser.parse_args()

    # Obter segment_duration do config.json
    config = get_config()
    segment_duration = config.get("segment_duration", 3)
    logging.debug(
        f"[DEBUG main_new.py] segment_duration from config: {segment_duration}"
    )

    # Obter imagens da configuração
    images = get_images_from_config()
    if not images:
        print("❌ Nenhuma imagem encontrada na pasta configurada")
        return 1

    # Preparar overlays com opacidade customizada
    overlays = []
    if args.overlay1:
        opacidade1 = getattr(args, "overlay1_opacidade", 0.4)
        overlays.append({"path": args.overlay1, "opacidade": opacidade1})
    if args.overlay2:
        opacidade2 = getattr(args, "overlay2_opacidade", 0.4)
        overlays.append({"path": args.overlay2, "opacidade": opacidade2})

    # Coletar overlays de vídeo chromakey
    overlays_chromakey = []
    for i in range(1, 6):
        path = getattr(args, f"chroma_video{i}", None)
        if path:
            overlays_chromakey.append(
                {
                    "path": path,
                    "start": getattr(args, f"chroma_start{i}", 0.0),
                    "position": getattr(args, f"chroma_pos{i}", "center"),
                    "chromakey": getattr(args, f"chroma_key{i}", None),
                }
            )

    # Criar requisição
    request = VideoCreationRequest(
        audio_path=Path(args.audio).resolve(),
        images=images,
        output_path=Path(args.saida).resolve(),
        segment_duration=segment_duration,
        transition=args.transicao if args.transicao != "none" else None,
        encoder=args.encoder,
        background_music_path=(
            Path(args.musica_fundo).resolve() if args.musica_fundo else None
        ),
        background_music_volume=args.volume_musica,
        logo_path=Path(args.logo).resolve() if args.logo else None,
        logo_position=args.logo_posicao,
        logo_opacity=args.logo_opacidade,
        logo_scale=args.logo_tamanho,
        overlays=overlays if overlays else None,
        overlays_chromakey=overlays_chromakey if overlays_chromakey else None,
        cover_path=Path(args.capa).resolve() if args.capa else None,
        cover_opacity=args.capa_opacidade,
        cover_size=args.capa_tamanho,
        cover_position=args.capa_posicao,
    )

    try:
        # Criar serviço e executar
        service = VideoCreationService()
        result_path = service.create_video(request)

        print(f"✅ Vídeo criado com sucesso: {result_path}")
        return 0

    except Exception as e:
        print(f"❌ Erro na criação do vídeo: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
