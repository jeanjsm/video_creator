# -*- coding: utf-8 -*-
"""
Video builder (FULL, clean)
- Corrige o erro "No such filter: '0:v'" (sempre colcheta rótulos no filter graph)
- Posicionamento da CAPA com normalização (bottom_right, etc.)
- Mantém suporte a logo, overlays, chroma e transições (single pass no vídeo)
- Mapeamento de áudio estável (narração + BGM)
- Código limpo e consistente (sem blocos duplicados/quebrados)
"""


import os
import math
import json
import shutil
import subprocess
from app.infra.logging import get_logger

# ==========================
# Utilitários de mídia
# ==========================


def _resolve_bin(name: str, user_path: str | None):
    if user_path and os.path.exists(user_path):
        return os.path.abspath(user_path)
    return name  # assume no PATH


def get_audio_duration(audio_path, ffprobe_path=None) -> float:
    if not audio_path:
        return 0.0
    ffprobe = _resolve_bin("ffprobe", ffprobe_path)
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                audio_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def get_image_size(img_path, ffprobe_path=None):
    ffprobe = _resolve_bin("ffprobe", ffprobe_path)
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "json",
                str(img_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        s = json.loads(result.stdout)["streams"][0]
        return int(s["width"]), int(s["height"])
    except Exception:
        return 1280, 720


# ==========================
# Helpers de filter graph / posições
# ==========================


def _as_link(s: str) -> str:
    """Garante que rótulos/streams usados em filter_complex tenham colchetes.
    Ex.: '0:v' -> '[0:v]'; '[vout]' fica igual.
    """
    if not s:
        return s
    s = str(s).strip()
    return s if s.startswith("[") else f"[{s}]"


def _norm_pos(p):
    if p is None:
        return "center"
    p = str(p).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "centro": "center",
        "meio": "center",
        "middle": "center",
        "c": "center",
        "top": "top_center",
        "tc": "top_center",
        "bottom": "bottom_center",
        "bc": "bottom_center",
        "tl": "top_left",
        "tr": "top_right",
        "bl": "bottom_left",
        "br": "bottom_right",
        "inferior_direita": "bottom_right",
        "direita_baixo": "bottom_right",
    }
    return aliases.get(p, p)


def _xy_from_pos(pos_key: str):
    pos = _norm_pos(pos_key)
    mapping = {
        "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
        "top_left": ("0", "0"),
        "top_right": ("main_w-overlay_w", "0"),
        "bottom_left": ("0", "main_h-overlay_h"),
        "bottom_right": ("main_w-overlay_w", "main_h-overlay_h"),
        "bottom_center": ("(main_w-overlay_w)/2", "main_h-overlay_h"),
        "top_center": ("(main_w-overlay_w)/2", "0"),
    }
    return mapping.get(pos, mapping["center"])


def _overlay_chain(
    last_video_map: str, src_label: str, x: str, y: str, out_label: str
) -> str:
    return f"{_as_link(last_video_map)}[{src_label}]overlay={x}:{y}:format=auto[{out_label}]"


# ==========================
# Flags de encoder
# ==========================


def get_encoder_flags(encoder: str, framerate: int = 30):
    enc = (encoder or "").lower()
    if enc == "libx264":
        return [
            "-preset",
            "veryfast",
            "-tune",
            "stillimage",
            "-crf",
            "26",
            "-g",
            str(framerate * 2),
        ]
    if enc == "h264_nvenc":
        return [
            "-preset",
            "p5",
            "-rc",
            "constqp",
            "-qp",
            "23",
            "-g",
            str(framerate * 2),
            "-bf",
            "2",
        ]
    if enc == "h264_qsv":
        return ["-global_quality", "23", "-look_ahead", "0", "-g", str(framerate * 2)]
    if enc == "h264_amf":
        return ["-quality", "speed", "-g", str(framerate * 2)]
    if enc in ("libvpx", "libvpx-vp9"):
        return ["-b:v", "2M", "-g", str(framerate * 2)]
    return []


# ==========================
# Áudio helpers
# ==========================


def build_audio_inputs(audio_path, background_music_path, dur_audio):
    inputs = []
    if audio_path:
        inputs += ["-i", audio_path]
    if background_music_path:
        inputs += [
            "-stream_loop",
            "-1",
            "-t",
            str(max(1.0, dur_audio)),
            "-i",
            background_music_path,
        ]
    return inputs


# ==========================
# Overlay de logo (compatível com _as_link)
# ==========================


def build_logo_args_and_filter(
    logo_path,
    logo_pos,
    logo_opacity,
    logo_scale,
    *,
    logo_input_idx: int,
    base_video_idx: int = 0,
):
    if not logo_path:
        return [], None, f"{base_video_idx}:v"
    x, y = _xy_from_pos(logo_pos)
    scale_expr = f"iw*{logo_scale}:ih*{logo_scale}"
    prep_logo = f"[{logo_input_idx}:v]scale={scale_expr},format=rgba,colorchannelmixer=aa={logo_opacity}[logo]"
    overlay = (
        f'{_as_link(f"{base_video_idx}:v")}[logo]overlay={x}:{y}:format=auto[outv]'
    )
    return ["-i", logo_path], f"{prep_logo};{overlay}", "[outv]"


# ==========================
# Renderizadores de segmentos
# ==========================


def render_none(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2"
    return [
        ffmpeg_path,
        "-y",
        "-loop",
        "1",
        "-t",
        str(segment_duration),
        "-i",
        os.path.abspath(img),
        "-vf",
        vf,
        "-r",
        str(framerate),
        "-c:v",
        encoder,
        *get_encoder_flags(encoder, framerate),
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-an",
        out_file,
    ]


def render_simplezoom(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    d_frames = int(segment_duration * framerate)
    zoom_expr = (
        f"zoom='1+0.1*on/{d_frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={d_frames}:s=1280x720:fps={framerate}"
    )
    vf = f"scale=1280:720,zoompan={zoom_expr}"
    return [
        ffmpeg_path,
        "-y",
        "-loop",
        "1",
        "-i",
        os.path.abspath(img),
        "-vf",
        vf,
        "-c:v",
        encoder,
        *get_encoder_flags(encoder, framerate),
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-frames:v",
        str(d_frames),
        out_file,
    ]


def render_fade(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    fade = min(1, segment_duration / 2)
    vf = f"scale=1280:720,fade=t=in:st=0:d={fade},fade=t=out:st={segment_duration - fade}:d={fade}"
    return [
        ffmpeg_path,
        "-y",
        "-loop",
        "1",
        "-t",
        str(segment_duration),
        "-i",
        os.path.abspath(img),
        "-vf",
        vf,
        "-r",
        str(framerate),
        "-c:v",
        encoder,
        *get_encoder_flags(encoder, framerate),
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-an",
        out_file,
    ]


def render_zoom(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    d_frames = int(segment_duration * framerate)
    zoom_expr = (
        f"zoom='if(lte(on,1),1,1+0.1*on/{d_frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={d_frames}:s=1280x720:fps={framerate}"
    )
    vf = f"scale=1280:720,zoompan={zoom_expr}"
    return [
        ffmpeg_path,
        "-y",
        "-loop",
        "1",
        "-i",
        os.path.abspath(img),
        "-vf",
        vf,
        "-c:v",
        encoder,
        *get_encoder_flags(encoder, framerate),
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-frames:v",
        str(d_frames),
        out_file,
    ]


def render_pendulo(
    img, out_file, segment_duration, ffmpeg_path, encoder, framerate, ffprobe_path=None
):
    w, h = get_image_size(img, ffprobe_path)
    r = h / w if w else 9 / 16

    strength, twist, speed, sharpen = 5, 5, 12, 30
    final_width, final_height = 1920, 1080

    A_deg = 12 * (max(0, min(100, strength)) / 100.0)
    freq = 0.2 + 1.8 * (max(0, min(100, speed)) / 100.0)
    sh = 0.30 * (max(0, min(100, twist)) / 100.0)
    amt = 1.50 * (max(0, min(100, sharpen)) / 100.0)

    def zoom_needed(theta, aspect):
        c = abs(math.cos(theta))
        s = abs(math.sin(theta))
        return max(c + aspect * s, s + (1.0 / aspect) * c)

    ZOOM = zoom_needed(math.radians(A_deg), r) * 1.06
    A_expr = f"({A_deg}*PI/180)"

    vf = (
        f"scale=iw*{ZOOM}:ih*{ZOOM}:flags=fast_bilinear,"
        f"shear=shx={sh}:shy=-{sh},"
        f"rotate={A_expr}*sin(2*PI*{freq}*t):ow=iw:oh=ih:bilinear=0,"
        f"unsharp=7:7:{amt}:7:7:0,"
        f"crop={final_width}:{final_height},"
        f"pad=ceil(iw/2)*2:ceil(ih/2)*2,setsar=1"
    )

    return [
        ffmpeg_path,
        "-y",
        "-loop",
        "1",
        "-t",
        str(segment_duration),
        "-i",
        os.path.abspath(img),
        "-vf",
        vf,
        "-r",
        str(framerate),
        "-c:v",
        encoder,
        *get_encoder_flags(encoder, framerate),
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "0",
        "-filter_threads",
        "0",
        "-an",
        out_file,
    ]


# ==========================
# Concatenação com transições (single pass, vídeo)
# ==========================


def concat_with_transitions_singlepass(
    segment_files,
    saida,
    segment_duration,
    ffmpeg_path,
    encoder,
    tipo_transicao="fade",
    transition=None,
):
    if transition is None:
        transition = min(1.0, segment_duration * 0.3)

    workdir = os.path.dirname(os.path.abspath(saida)) or "."
    concat_list = os.path.join(workdir, "concat_segments.txt")
    graph_path = os.path.join(workdir, "xfade_graph.txt")

    with open(concat_list, "w", encoding="utf-8") as f:
        for seg in segment_files:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    n = len(segment_files)
    lines = []
    for i in range(n):
        start = i * segment_duration
        end = start + segment_duration
        lines.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")

    if n == 1:
        lines.append("[v0]copy[vout]")
    else:
        prev = "[v0]"
        for i in range(1, n):
            off = i * segment_duration - i * transition
            lines.append(
                f"{prev}[v{i}]xfade=transition={tipo_transicao}:duration={transition}:offset={off}[x{i}]"
            )
            prev = f"[x{i}]"
        lines.append(f"{prev}copy[vout]")

    with open(graph_path, "w", encoding="utf-8") as f:
        f.write(";\n".join(lines))

    cmd = [
        ffmpeg_path,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_list,
        "-filter_complex_script",
        graph_path,
        "-map",
        "[vout]",
        "-c:v",
        encoder,
        *get_encoder_flags(encoder, framerate=30),
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        "-movflags",
        "+faststart",
        saida,
    ]

    subprocess.run(cmd, check=True)

    try:
        os.remove(concat_list)
        os.remove(graph_path)
    except Exception:
        pass


# ==========================
# Função principal
# ==========================


def criar_video(
    audio_path,
    imagens,
    saida,
    segment_duration=3,
    transicao=None,
    efeito="fade",
    encoder="libx264",
    ffmpeg_path=None,
    ffprobe_path=None,
    background_music_path=None,
    background_music_volume=0.2,
    logo_path=None,
    logo_pos="top_left",
    logo_opacity=1.0,
    logo_scale=0.15,
    overlays=None,
    capa=None,
    capa_opacidade=1.0,
    capa_tamanho=1.0,
    capa_posicao="centro",
    overlay_chromas=None,
):
    logger = get_logger("criar_video")
    logger.info(
        "Iniciando criação do vídeo: saída=%s, imagens=%d, áudio=%s",
        saida,
        len(imagens),
        audio_path,
    )
    ffmpeg_path = _resolve_bin("ffmpeg", ffmpeg_path)
    ffprobe_path = _resolve_bin("ffprobe", ffprobe_path)

    dur_audio = get_audio_duration(audio_path, ffprobe_path) if audio_path else 0.0
    imagens_repetidas = list(imagens)

    # ===== SEM TRANSIÇÃO =====
    if not transicao:
        lista_imagens = "imagens.txt"
        with open(lista_imagens, "w", encoding="utf-8") as f:
            total = 0.0
            for img in imagens_repetidas:
                if dur_audio and total >= dur_audio:
                    break
                f.write(f"file '{os.path.abspath(img)}'\n")
                f.write(f"duration {segment_duration}\n")
                total += segment_duration
            if imagens_repetidas:
                f.write(f"file '{os.path.abspath(imagens_repetidas[-1])}'\n")

        cmd = [ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", lista_imagens]
        input_count = 1  # 0 = vídeo

        # Áudio
        cmd += build_audio_inputs(audio_path, background_music_path, dur_audio)
        narr_idx = input_count if audio_path else None
        input_count += 1 if audio_path else 0
        bgm_idx = input_count if background_music_path else None
        input_count += 1 if background_music_path else 0

        # Overlays
        overlay_filters, overlay_inputs = [], []
        last_video_map = "0:v"
        next_input_idx = input_count

        # Logo (abaixo da capa)
        if logo_path:
            logger.info("Adicionando logo: %s", logo_path)
            logo_input_idx = next_input_idx
            overlay_inputs += ["-i", logo_path]
            next_input_idx += 1
            # Usa base 0:v pois ainda não houve outro overlay
            x, y = _xy_from_pos(logo_pos)
            scale_expr = f"iw*{logo_scale}:ih*{logo_scale}"
            prep_logo = f"[{logo_input_idx}:v]scale={scale_expr},format=rgba,colorchannelmixer=aa={logo_opacity}[logo]"
            overlay_logo = f'{_as_link("0:v")}[logo]overlay={x}:{y}:format=auto[outv]'
            overlay_filters += [prep_logo, overlay_logo]
            last_video_map = "[outv]"

        # Outros overlays simples
        if overlays:
            for ov in overlays:
                if not ov.get("path"):
                    continue
                logger.info("Adicionando overlay: %s", ov["path"])
                ov_path = ov["path"]
                ov_opac = float(ov.get("opacidade", 1.0))
                is_video = os.path.splitext(ov_path)[1].lower() in {
                    ".mp4",
                    ".mov",
                    ".avi",
                    ".mkv",
                    ".webm",
                }
                if is_video:
                    overlay_inputs += ["-stream_loop", "-1", "-i", ov_path]
                else:
                    overlay_inputs += ["-i", ov_path]
                ov_idx = next_input_idx
                next_input_idx += 1
                ov_label = f"ov{ov_idx}"
                prep_ov = f"[{ov_idx}:v]scale=1280:720,format=rgba,colorchannelmixer=aa={ov_opac}[{ov_label}]"
                out_label = f"outv{ov_idx}"
                overlay = _overlay_chain(last_video_map, ov_label, "0", "0", out_label)
                overlay_filters += [prep_ov, overlay]
                last_video_map = f"[{out_label}]"

        # Overlays chroma key
        if overlay_chromas:
            for chroma in overlay_chromas:
                cpath = chroma.get("path")
                if not cpath:
                    continue
                logger.info("Adicionando overlay chroma: %s", cpath)
                c_start = float(chroma.get("start", 0))
                c_opac = float(chroma.get("opacidade", chroma.get("opacity", 1.0)))
                c_tol = float(chroma.get("tolerancia", chroma.get("tolerance", 0.2)))
                c_pos = chroma.get("position", "bottom_center")
                c_size = float(chroma.get("size", 1.0))
                # duração do overlay chroma
                c_dur = get_audio_duration(cpath, ffprobe_path)
                if c_dur <= 0:
                    try:
                        ffprobe = _resolve_bin("ffprobe", ffprobe_path)
                        r = subprocess.run(
                            [
                                ffprobe,
                                "-v",
                                "error",
                                "-show_entries",
                                "format=duration",
                                "-of",
                                "json",
                                cpath,
                            ],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        c_dur = float(json.loads(r.stdout)["format"]["duration"])
                    except Exception:
                        c_dur = 0.0
                overlay_inputs += ["-i", cpath]
                c_idx = next_input_idx
                next_input_idx += 1
                x, y = _xy_from_pos(c_pos)
                scale_expr = f"iw*{c_size}:ih*{c_size}"
                enable_expr = f"enable='between(t,{c_start},{c_start+c_dur})'"
                c_label = f"chroma{c_idx}"
                prep_c = f"[{c_idx}:v]scale={scale_expr},chromakey=0x00FF00:{c_tol}:0.1,format=rgba,colorchannelmixer=aa={c_opac}[{c_label}]"
                out_label = f"outv{c_idx}"
                overlay_c = f"{_as_link(last_video_map)}[{c_label}]overlay={x}:{y}:format=auto:{enable_expr}[{out_label}]"
                overlay_filters += [prep_c, overlay_c]
                last_video_map = f"[{out_label}]"

        # CAPA por cima de tudo
        if capa:
            overlay_inputs += ["-i", capa]
            capa_idx = next_input_idx
            next_input_idx += 1
            x, y = _xy_from_pos(capa_posicao)
            scale_expr = f"iw*{capa_tamanho}:ih*{capa_tamanho}"
            capa_label = f"capa{capa_idx}"
            prep_capa = f"[{capa_idx}:v]scale={scale_expr},format=rgba,colorchannelmixer=aa={capa_opacidade}[{capa_label}]"
            out_label = f"outv{capa_idx}"
            overlay = _overlay_chain(last_video_map, capa_label, x, y, out_label)
            overlay_filters += [prep_capa, overlay]
            last_video_map = f"[{out_label}]"

        cmd += overlay_inputs

        # Mix de áudio / filtros
        filter_parts = [f for f in overlay_filters if f]
        audio_map = None
        if narr_idx is not None and bgm_idx is not None:
            filter_parts.append(
                f"[{narr_idx}:a]volume=1[a0];[{bgm_idx}:a]volume={background_music_volume}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            audio_map = "[aout]"
        elif narr_idx is not None:
            audio_map = f"{narr_idx}:a"
        elif bgm_idx is not None:
            audio_map = f"{bgm_idx}:a"

        cmd += [
            "-c:v",
            encoder,
            *get_encoder_flags(encoder, framerate=30),
            "-pix_fmt",
            "yuv420p",
        ]
        if filter_parts:
            cmd += ["-filter_complex", ";".join(filter_parts), "-map", last_video_map]
        else:
            cmd += ["-map", "0:v"]
        if audio_map:
            cmd += ["-map", audio_map, "-c:a", "aac"]
        else:
            cmd += ["-an"]
        if dur_audio > 0:
            cmd += ["-t", str(dur_audio)]
        cmd += ["-shortest", "-movflags", "+faststart", saida]

        subprocess.run(cmd, check=True)
        try:
            os.remove(lista_imagens)
        except Exception:
            pass
        return

    # ===== COM TRANSIÇÃO =====
    pre_dir = os.path.join(
        os.path.dirname(os.path.abspath(saida)), "pre_rendered_image_segments"
    )
    os.makedirs(pre_dir, exist_ok=True)

    imagens_unicas = list(dict.fromkeys(imagens))
    fr = 30
    segs_unicos = []
    for img in imagens_unicas:
        out_file = os.path.join(pre_dir, os.path.basename(img) + f"_{efeito}.mp4")
        if efeito == "fade":
            cmd_r = render_fade(
                img, out_file, segment_duration, ffmpeg_path, encoder, fr
            )
        elif efeito == "zoom":
            cmd_r = render_zoom(
                img, out_file, segment_duration, ffmpeg_path, encoder, fr
            )
        elif efeito == "simplezoom":
            cmd_r = render_simplezoom(
                img, out_file, segment_duration, ffmpeg_path, encoder, fr
            )
        elif efeito == "pendulo":
            cmd_r = render_pendulo(
                img, out_file, segment_duration, ffmpeg_path, encoder, fr, ffprobe_path
            )
        else:
            cmd_r = render_none(
                img, out_file, segment_duration, ffmpeg_path, encoder, fr
            )
        subprocess.run(cmd_r, check=True)
        segs_unicos.append(out_file)

    seg_map = dict(zip(imagens_unicas, segs_unicos))
    segment_files = [seg_map[i] for i in imagens_repetidas]

    temp_video = saida + ".tmpvideo.mp4"
    tipo_transicao = transicao if isinstance(transicao, str) else "fade"
    concat_with_transitions_singlepass(
        segment_files,
        saida=temp_video,
        segment_duration=segment_duration,
        ffmpeg_path=ffmpeg_path,
        encoder=encoder,
        tipo_transicao=tipo_transicao,
        transition=None,
    )

    # Segunda passada: overlays + áudio
    cmd = [ffmpeg_path, "-y", "-i", temp_video]
    input_count = 1

    cmd += build_audio_inputs(audio_path, background_music_path, dur_audio)
    narr_idx = input_count if audio_path else None
    input_count += 1 if audio_path else 0
    bgm_idx = input_count if background_music_path else None
    input_count += 1 if background_music_path else 0

    overlay_filters, overlay_inputs = [], []
    last_video_map = "0:v"
    next_input_idx = input_count

    # Logo (abaixo da capa)
    if logo_path:
        logo_input_idx = next_input_idx
        overlay_inputs += ["-i", logo_path]
        next_input_idx += 1
        x, y = _xy_from_pos(logo_pos)
        scale_expr = f"iw*{logo_scale}:ih*{logo_scale}"
        prep_logo = f"[{logo_input_idx}:v]scale={scale_expr},format=rgba,colorchannelmixer=aa={logo_opacity}[logo]"
        overlay_logo = f'{_as_link("0:v")}[logo]overlay={x}:{y}:format=auto[outv]'
        overlay_filters += [prep_logo, overlay_logo]
        last_video_map = "[outv]"

    # Outros overlays
    if overlays:
        for ov in overlays:
            if not ov.get("path"):
                continue
            ov_path = ov["path"]
            ov_opac = float(ov.get("opacidade", 1.0))
            is_video = os.path.splitext(ov_path)[1].lower() in {
                ".mp4",
                ".mov",
                ".avi",
                ".mkv",
                ".webm",
            }
            if is_video:
                overlay_inputs += ["-stream_loop", "-1", "-i", ov_path]
            else:
                overlay_inputs += ["-i", ov_path]
            ov_idx = next_input_idx
            next_input_idx += 1
            ov_label = f"ov{ov_idx}"
            prep_ov = f"[{ov_idx}:v]scale=1280:720,format=rgba,colorchannelmixer=aa={ov_opac}[{ov_label}]"
            out_label = f"outv{ov_idx}"
            overlay = _overlay_chain(last_video_map, ov_label, "0", "0", out_label)
            overlay_filters += [prep_ov, overlay]
            last_video_map = f"[{out_label}]"

    # Overlays chroma key
    if overlay_chromas:
        for chroma in overlay_chromas:
            cpath = chroma.get("path")
            if not cpath:
                continue
            c_start = float(chroma.get("start", 0))
            c_opac = float(chroma.get("opacidade", chroma.get("opacity", 1.0)))
            c_tol = float(chroma.get("tolerancia", chroma.get("tolerance", 0.2)))
            c_pos = chroma.get("position", "bottom_center")
            c_size = float(chroma.get("size", 1.0))
            c_dur = get_audio_duration(cpath, ffprobe_path)
            if c_dur <= 0:
                try:
                    ffprobe = _resolve_bin("ffprobe", ffprobe_path)
                    r = subprocess.run(
                        [
                            ffprobe,
                            "-v",
                            "error",
                            "-show_entries",
                            "format=duration",
                            "-of",
                            "json",
                            cpath,
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    c_dur = float(json.loads(r.stdout)["format"]["duration"])
                except Exception:
                    c_dur = 0.0
            overlay_inputs += ["-i", cpath]
            c_idx = next_input_idx
            next_input_idx += 1
            x, y = _xy_from_pos(c_pos)
            scale_expr = f"iw*{c_size}:ih*{c_size}"
            enable_expr = f"enable='between(t,{c_start},{c_start+c_dur})'"
            c_label = f"chroma{c_idx}"
            prep_c = f"[{c_idx}:v]scale={scale_expr},chromakey=0x00FF00:{c_tol}:0.1,format=rgba,colorchannelmixer=aa={c_opac}[{c_label}]"
            out_label = f"outv{c_idx}"
            overlay_c = f"{_as_link(last_video_map)}[{c_label}]overlay={x}:{y}:format=auto:{enable_expr}[{out_label}]"
            overlay_filters += [prep_c, overlay_c]
            last_video_map = f"[{out_label}]"

    # CAPA por cima de tudo
    if capa:
        overlay_inputs += ["-i", capa]
        capa_idx = next_input_idx
        next_input_idx += 1
        x, y = _xy_from_pos(capa_posicao)
        scale_expr = f"iw*{capa_tamanho}:ih*{capa_tamanho}"
        capa_label = f"capa{capa_idx}"
        prep_capa = f"[{capa_idx}:v]scale={scale_expr},format=rgba,colorchannelmixer=aa={capa_opacidade}[{capa_label}]"
        out_label = f"outv{capa_idx}"
        overlay = _overlay_chain(last_video_map, capa_label, x, y, out_label)
        overlay_filters += [prep_capa, overlay]
        last_video_map = f"[{out_label}]"

    cmd += overlay_inputs

    # Mix de áudio / filtros finais
    filter_parts = [f for f in overlay_filters if f]
    audio_map = None
    if narr_idx is not None and bgm_idx is not None:
        filter_parts.append(
            f"[{narr_idx}:a]volume=1[a0];[{bgm_idx}:a]volume={background_music_volume}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        audio_map = "[aout]"
    elif narr_idx is not None:
        audio_map = f"{narr_idx}:a"
    elif bgm_idx is not None:
        audio_map = f"{bgm_idx}:a"

    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts), "-map", last_video_map]
        cmd += [
            "-c:v",
            encoder,
            *get_encoder_flags(encoder, framerate=30),
            "-pix_fmt",
            "yuv420p",
        ]
    else:
        cmd += ["-map", "0:v", "-c:v", "copy"]

    if audio_map:
        cmd += ["-map", audio_map, "-c:a", "aac"]
    else:
        cmd += ["-an"]

    if dur_audio > 0:
        cmd += ["-t", str(dur_audio)]
    cmd += ["-shortest", "-movflags", "+faststart", saida]

    logger.info("Comando FFmpeg: %s", " ".join(map(str, cmd)))
    try:
        subprocess.run(cmd, check=True)
        logger.info("Vídeo criado com sucesso: %s", saida)
    except Exception as e:
        logger.error("Erro ao executar FFmpeg: %s", e, exc_info=True)
        raise
