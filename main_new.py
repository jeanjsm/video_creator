"""
main_new.py — Interface CLI seguindo Clean Architecture com suporte a legendas
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
from app.domain.models.subtitle import SubtitleStyle


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


def create_subtitle_style(args, config: dict = None) -> SubtitleStyle:
    """Cria estilo de legenda baseado nos argumentos CLI e config.json

    Prioridade: CLI > config.json > padrões hardcoded
    """
    # Obter configurações de legenda do config.json
    subtitle_config = config.get("subtitles", {}).get("style", {}) if config else {}

    # Verificar se argumentos foram explicitamente fornecidos via CLI
    # (argparse sempre define valores padrão, então verificamos se não são os padrões)
    def get_value_with_priority(cli_attr, config_key, default_value):
        cli_value = getattr(args, cli_attr, default_value)
        # Se o valor CLI é diferente do padrão, usar CLI
        # Senão, usar config.json, senão usar padrão
        if cli_value != default_value:
            return cli_value
        return subtitle_config.get(config_key, default_value)

    # CLI tem prioridade, senão usa config.json, senão usa padrões
    return SubtitleStyle(
        font_size=get_value_with_priority('subtitle_font_size', 'font_size', 24),
        font_color=get_value_with_priority('subtitle_color', 'font_color', 'white'),
        background_color=get_value_with_priority('subtitle_background', 'background_color', 'black@0.5'),
        position=get_value_with_priority('subtitle_position', 'position', 'bottom_center'),
        margin_bottom=get_value_with_priority('subtitle_margin', 'margin_bottom', 50),
        max_chars_per_line=get_value_with_priority('subtitle_max_chars', 'max_chars_per_line', 60),
        max_words_per_line=get_value_with_priority('subtitle_max_words', 'max_words_per_line', 4),
        outline_width=get_value_with_priority('subtitle_outline_width', 'outline_width', 2),
        outline_color=get_value_with_priority('subtitle_outline_color', 'outline_color', 'black'),
        # Novas opções de fonte (None é o padrão, então pode usar diretamente)
        font_file=getattr(args, 'subtitle_font_file', None) or subtitle_config.get("font_file", None),
        font_family=getattr(args, 'subtitle_font_family', None) or subtitle_config.get("font_family", None),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Cria um vídeo a partir de uma narração e imagens usando FFmpeg."
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

    # === ARGUMENTOS DE LEGENDA ===
    parser.add_argument(
        "--legendas",
        action="store_true",
        help="Habilitar legendas automáticas usando Vosk",
    )
    parser.add_argument(
        "--vosk_model",
        type=str,
        help="Caminho para o modelo Vosk (padrão: busca automática)",
    )
    parser.add_argument(
        "--subtitle_confidence",
        type=float,
        default=0.5,
        help="Limiar de confiança para legendas (0.0 a 1.0, padrão: 0.5)",
    )
    parser.add_argument(
        "--subtitle_max_duration",
        type=float,
        default=4.0,
        help="Duração máxima de cada segmento de legenda em segundos (padrão: 4.0)",
    )

    # Estilo das legendas
    parser.add_argument(
        "--subtitle_font_size",
        type=int,
        default=24,
        help="Tamanho da fonte das legendas (padrão: 24)",
    )
    parser.add_argument(
        "--subtitle_color",
        type=str,
        default="white",
        help="Cor da fonte das legendas (padrão: white)",
    )
    parser.add_argument(
        "--subtitle_background",
        type=str,
        default="black@0.5",
        help="Cor de fundo das legendas (padrão: black@0.5)",
    )
    parser.add_argument(
        "--subtitle_position",
        choices=["bottom_center", "top_center", "center"],
        default="bottom_center",
        help="Posição das legendas (padrão: bottom_center)",
    )
    parser.add_argument(
        "--subtitle_margin",
        type=int,
        default=50,
        help="Margem inferior das legendas em pixels (padrão: 50)",
    )
    parser.add_argument(
        "--subtitle_max_chars",
        type=int,
        default=60,
        help="Máximo de caracteres por linha de legenda (padrão: 60)",
    )
    parser.add_argument(
        "--subtitle_max_words",
        type=int,
        default=4,
        help="Máximo de palavras por linha de legenda (padrão: 4)",
    )
    parser.add_argument(
        "--subtitle_outline_width",
        type=int,
        default=2,
        help="Largura do contorno das legendas (padrão: 2)",
    )
    parser.add_argument(
        "--subtitle_outline_color",
        type=str,
        default="black",
        help="Cor do contorno das legendas (padrão: black)",
    )

    # === NOVAS OPÇÕES DE FONTE ===
    parser.add_argument(
        "--subtitle_font_file",
        type=str,
        help="Caminho para arquivo de fonte (.ttf, .otf) - ex: ./fonts/arial.ttf",
    )
    parser.add_argument(
        "--subtitle_font_family",
        type=str,
        help="Nome da família de fonte do sistema - ex: 'Arial', 'Times New Roman'",
    )

    # Overlays de vídeo com chromakey
    for i in range(1, 6):  # Suporte até 5 overlays
        parser.add_argument(f"--chroma_video{i}", help=f"Overlay de vídeo chromakey {i}")
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

    args = parser.parse_args()

    # Carregar config
    config = get_config()

    # Definir enable_subtitles: CLI tem prioridade, senão usa config
    # Para action="store_true", args.legendas é False por padrão, não None
    # Se foi passado --legendas na CLI, usar True
    # Se não foi passado --legendas na CLI, verificar config.json
    enable_subtitles = args.legendas or config.get("subtitles", {}).get("enabled", False)

    # Coletar overlays chromakey
    overlays_chromakey = []
    for i in range(1, 4):
        path = getattr(args, f"chroma_video{i}", None)
        if path:
            overlays_chromakey.append({
                "path": path,
                "start": getattr(args, f"chroma_start{i}", 0.0),
                "position": getattr(args, f"chroma_pos{i}", "center"),
                "chromakey": getattr(args, f"chroma_key{i}", None),
            })

    # Verificação de dependências para legendas
    if enable_subtitles:
        try:
            import vosk
            print("✅ Vosk disponível para legendas")
        except ImportError:
            print("❌ Vosk não está instalado. Para usar legendas, instale com: pip install vosk")
            print("   Vídeo será criado sem legendas.")
            enable_subtitles = False

    # Obter segment_duration do config.json
    segment_duration = config.get("segment_duration", 3)
    logging.debug(f"[DEBUG main_new.py] segment_duration from config: {segment_duration}")

    # Obter imagens da configuração
    images = get_images_from_config()
    if not images:
        print("❌ Nenhuma imagem encontrada na pasta configurada")
        return 1

    # Preparar overlays com opacidade customizada
    overlays = []
    if args.overlay1:
        overlays.append({"path": args.overlay1, "opacidade": args.overlay1_opacidade})
    if args.overlay2:
        overlays.append({"path": args.overlay2, "opacidade": args.overlay2_opacidade})

    # Criar estilo de legenda se habilitado
    subtitle_style = None
    if enable_subtitles:
        subtitle_style = create_subtitle_style(args, config)
        print(f"🎬 Legendas habilitadas: {subtitle_style.position}, fonte {subtitle_style.font_size}px")

    # Obter configurações de legenda do config.json para valores não fornecidos via CLI
    subtitle_config_root = config.get("subtitles", {})

    # Determinar valores finais com prioridade CLI > config.json > padrões
    # Para confidence e max_duration, verificamos se são diferentes dos padrões
    final_vosk_model = args.vosk_model or subtitle_config_root.get("vosk_model_path", "./vosk-model")
    final_confidence = args.subtitle_confidence if args.subtitle_confidence != 0.5 else subtitle_config_root.get("confidence_threshold", 0.5)
    final_max_duration = args.subtitle_max_duration if args.subtitle_max_duration != 4.0 else subtitle_config_root.get("max_segment_duration", 4.0)

    # Passar overlays_chromakey e enable_subtitles para o serviço de vídeo
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
        # Configurações de legenda
        enable_subtitles=enable_subtitles,
        subtitle_style=subtitle_style,
        vosk_model_path=Path(final_vosk_model).resolve() if final_vosk_model else None,
        subtitle_confidence_threshold=final_confidence,
        subtitle_max_duration=final_max_duration,
    )

    try:
        # Criar serviço e executar
        service = VideoCreationService()
        result_path = service.create_video(request)

        print(f"✅ Vídeo criado com sucesso: {result_path}")
        if enable_subtitles:
            print("📝 Legendas foram aplicadas automaticamente")
        return 0

    except Exception as e:
        print(f"❌ Erro na criação do vídeo: {e}")
        logging.exception("Erro detalhado:")
        return 1


if __name__ == "__main__":
    exit(main())