# ==========================
# Função principal de criação de vídeo (exportável)
# ==========================

def criar_video(audio_path, imagens, saida, segment_duration=3, transicao=None, efeito='fade', encoder='libx264', ffmpeg_path=None, ffprobe_path=None):
    """
    Função principal para criar vídeo sincronizado com narração e imagens.
    ffmpeg_path e ffprobe_path são obrigatórios (injeção de dependência).
    """
    if ffmpeg_path is None or ffprobe_path is None:
        raise ValueError('ffmpeg_path e ffprobe_path devem ser fornecidos')

    # Descobre a duração do áudio
    dur_audio = get_audio_duration(audio_path, ffprobe_path)
    if dur_audio == 0:
        print("Não foi possível obter a duração do áudio.")
        return

    # Ajuste de contagem de imagens
    transition = min(1.0, segment_duration * 0.3) if transicao else 0
    if transicao:
        # Soma total: n*segment_duration - (n-1)*transition >= dur_audio
        n_imagens = max(2, int((dur_audio + transition) / (segment_duration - transition)) + 2)
    else:
        n_imagens = int(dur_audio // segment_duration) + 1

    imagens_repetidas = [imagens[i % len(imagens)] for i in range(n_imagens)]

    if not transicao:
        # Caminho simples (sem transição): concat demuxer de imagens estáticas
        lista_imagens = 'imagens.txt'
        with open(lista_imagens, 'w', encoding='utf-8') as f:
            for img in imagens_repetidas:
                f.write(f"file '{os.path.abspath(img)}'\n")
                f.write(f"duration {segment_duration}\n")
            f.write(f"file '{os.path.abspath(imagens_repetidas[-1])}'\n")
        cmd = [
            ffmpeg_path,
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', lista_imagens,
            '-i', audio_path,
            '-c:v', encoder, *get_encoder_flags(encoder, framerate=30),
            '-c:a', 'aac',
            '-pix_fmt', 'yuv420p',
            '-shortest',
            '-movflags', '+faststart',
            saida
        ]
        print(f"Executando: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
            print(f"Vídeo gerado com sucesso: {saida}")
        except subprocess.CalledProcessError as e:
            print(f"Erro ao gerar vídeo: {e}")
    else:
        # Pré-renderiza segmentos únicos com efeito (garante mesma resolução/fps)
        pre_dir = os.path.join(os.path.dirname(saida), 'pre_rendered_image_segments')
        imagens_unicas = list(dict.fromkeys(imagens))
        segment_map = {}

        # Renderiza cada imagem única uma vez (com cache)
        segment_files_unicos = pre_render_segments(imagens_unicas, segment_duration, pre_dir, efeito=efeito, encoder=encoder, ffmpeg_path=ffmpeg_path, ffprobe_path=ffprobe_path)
        for img, seg in zip(imagens_unicas, segment_files_unicos):
            segment_map[img] = seg

        # Monta a lista de segmentos na ordem correta
        segment_files = [segment_map[img] for img in imagens_repetidas]

        # SINGLE PASS: concat demuxer + trim + xfade + áudio
        try:
            tipo_transicao = transicao if isinstance(transicao, str) else 'fade'
            concat_with_transitions_singlepass(segment_files, audio_path=audio_path, saida=saida,
                                               segment_duration=segment_duration,
                                               ffmpeg_path=ffmpeg_path, encoder=encoder,
                                               tipo_transicao=tipo_transicao,
                                               transition=transition)
            print(f"Vídeo gerado com sucesso: {saida}")
        except subprocess.CalledProcessError as e:
            print(f"Erro ao gerar vídeo: {e}")

"""
Módulo core (domínio) — Clean Architecture
------------------------------------------
Contém apenas lógica de negócio e manipulação de vídeo, SEM acesso direto a arquivos de configuração, disco, OS, etc.
Todas as dependências externas (ffmpeg_path, ffprobe_path) são injetadas por parâmetro.
Não acessar config.json ou recursos externos diretamente!
"""

import math
import subprocess
import os
import shutil
import shlex
from pathlib import Path
import json
import hashlib

def get_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# ==========================
# Utilitários de mídia
# ==========================


def get_audio_duration(audio_path, ffprobe_path):
    """Retorna a duração do áudio em segundos usando ffprobe (ffprobe_path injetado)."""
    result = subprocess.run([
        ffprobe_path,
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0



def get_image_size(image_path: Path, ffprobe_path):
    """Usa ffprobe para obter largura e altura da imagem (ffprobe_path injetado)."""
    cmd = [
        ffprobe_path, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        str(image_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, check=True, text=True)
    data = json.loads(result.stdout)
    w = data["streams"][0]["width"]
    h = data["streams"][0]["height"]
    return w, h


def get_encoder_flags(encoder: str, framerate: int):
    """Retorna flags apropriadas para diferentes encoders visando velocidade/qualidade."""
    enc = (encoder or '').lower()
    if enc == 'libx264':
        # Boa qualidade e rapidez para still images
        return ['-preset', 'veryfast', '-tune', 'stillimage', '-crf', '26', '-g', str(framerate * 2)]
    if enc == 'h264_nvenc':
        # NVENC rápido e estável
        return ['-preset', 'p5', '-rc', 'constqp', '-qp', '23', '-g', str(framerate * 2), '-bf', '2']
    if enc == 'h264_qsv':
        # Intel QuickSync
        return ['-global_quality', '23', '-look_ahead', '0', '-g', str(framerate * 2)]
    if enc == 'h264_amf':
        # AMD AMF
        return ['-quality', 'speed', '-g', str(framerate * 2)]
    return []
    # ...existing code...
# Pré-render de segmentos (com cache)
# ==========================

def pre_render_segments(imagens, segment_duration, output_dir, efeito='fade', encoder='libx264'):
    """Pré-renderiza cada imagem como um segmento .mp4 com efeito (fade, zoom, pendulo, simplezoom) e encoder escolhido. Usa cache se os parâmetros não mudaram."""
def pre_render_segments(imagens, segment_duration, output_dir, efeito='fade', encoder='libx264', ffmpeg_path=None, ffprobe_path=None):
    """Pré-renderiza cada imagem como um segmento .mp4 com efeito (fade, zoom, pendulo, simplezoom) e encoder escolhido. Usa cache se os parâmetros não mudaram."""
    if ffmpeg_path is None:
        raise ValueError('ffmpeg_path deve ser fornecido')
    if ffprobe_path is None:
        raise ValueError('ffprobe_path deve ser fornecido')
    framerate = 30

    # Gera hash dos parâmetros relevantes (ordem e caminhos normalizados)
    imagens_abs = [os.path.normcase(os.path.abspath(img)) for img in imagens]
    param_dict = {
        'imagens': imagens_abs,
        'segment_duration': segment_duration,
        'efeito': efeito,
        'encoder': encoder,
        'framerate': framerate
    }
    param_str = json.dumps(param_dict, sort_keys=True, ensure_ascii=False)
    param_hash = hashlib.md5(param_str.encode('utf-8')).hexdigest()

    os.makedirs(output_dir, exist_ok=True)
    hash_file = os.path.join(output_dir, 'prerender.hash')

    # Cache válido?
    if os.path.exists(hash_file):
        try:
            with open(hash_file, 'r', encoding='utf-8') as f:
                old_hash = f.read().strip()
            segment_files = [os.path.join(output_dir, f'segment_{idx:04d}.mp4') for idx in range(len(imagens))]
            if old_hash == param_hash and all(os.path.exists(f) for f in segment_files):
                print(f"Pré-renderização já existente e válida em {output_dir}, reutilizando.")
                return segment_files
        except Exception:
            pass
        # cache inválido
        shutil.rmtree(output_dir, ignore_errors=True)
        os.makedirs(output_dir, exist_ok=True)

    segment_files = []
    for idx, img in enumerate(imagens):
        out_file = os.path.join(output_dir, f'segment_{idx:04d}.mp4')
        if efeito == 'zoom':
            cmd = render_zoom(img, out_file, segment_duration, ffmpeg_path, encoder, framerate)
        elif efeito == 'pendulo':
            cmd = render_pendulo(img, out_file, segment_duration, ffmpeg_path, encoder, framerate)
        elif efeito == 'simplezoom':
            cmd = render_simplezoom(img, out_file, segment_duration, ffmpeg_path, encoder, framerate)
        elif efeito == 'none':
            cmd = render_none(img, out_file, segment_duration, ffmpeg_path, encoder, framerate)
        else:
            cmd = render_fade(img, out_file, segment_duration, ffmpeg_path, encoder, framerate)
        print(f"Pré-renderizando segmento: {out_file} [{efeito}, {encoder}, {framerate}fps]")
        subprocess.run(cmd, check=True)
        segment_files.append(out_file)

    # Salva hash ao final do processo bem-sucedido
    try:
        with open(hash_file, 'w', encoding='utf-8') as f:
            f.write(param_hash)
    except Exception:
        pass

    return segment_files


# ==========================
# Renderizadores de segmentos
# ==========================

def render_none(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    """Renderiza a imagem sem efeito, apenas scale/pad."""
    vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2"
    extra_enc = get_encoder_flags(encoder, framerate)
    cmd = [
        ffmpeg_path,
        '-y',
        '-loop', '1',
        '-t', str(segment_duration),
        '-i', os.path.abspath(img),
        '-vf', vf,
        '-r', str(framerate),
        '-c:v', encoder, *extra_enc,
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        '-an',
        out_file
    ]
    return cmd


def render_simplezoom(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    """Zoom simples (in) durante o segmento."""
    d_frames = int(segment_duration * framerate)
    zoom_expr = f"zoom='1+0.1*on/{d_frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d_frames}:s=1280x720:fps={framerate}"
    vf = f"scale=1280:720,zoompan={zoom_expr}"
    extra_enc = get_encoder_flags(encoder, framerate)
    cmd = [
        ffmpeg_path,
        '-y',
        '-loop', '1',
        '-i', os.path.abspath(img),
        '-vf', vf,
        '-c:v', encoder, *extra_enc,
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        '-an',
        '-frames:v', str(d_frames),
        out_file
    ]
    return cmd


def render_fade(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    fade = min(1, segment_duration/2)
    vf = f"scale=1280:720,fade=t=in:st=0:d={fade},fade=t=out:st={segment_duration-fade}:d={fade}"
    extra_enc = get_encoder_flags(encoder, framerate)
    cmd = [
        ffmpeg_path,
        '-y',
        '-loop', '1',
        '-t', str(segment_duration),
        '-i', os.path.abspath(img),
        '-vf', vf,
        '-r', str(framerate),
        '-c:v', encoder, *extra_enc,
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        '-an',
        out_file
    ]
    return cmd


def render_zoom(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    d_frames = int(segment_duration * framerate)
    zoom_expr = f"zoom='if(lte(on,1),1,1+0.1*on/{d_frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d_frames}:s=1280x720:fps={framerate}"
    vf = f"scale=1280:720,zoompan={zoom_expr}"
    extra_enc = get_encoder_flags(encoder, framerate)
    cmd = [
        ffmpeg_path,
        '-y',
        '-loop', '1',
        '-i', os.path.abspath(img),
        '-vf', vf,
        '-c:v', encoder, *extra_enc,
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        '-an',
        '-frames:v', str(d_frames),
        out_file
    ]
    return cmd


def render_pendulo(img, out_file, segment_duration, ffmpeg_path, encoder, framerate):
    """Efeito pêndulo com pré-zoom e CROP final (zoom visível)."""
def render_pendulo(img, out_file, segment_duration, ffmpeg_path, encoder, framerate, ffprobe_path):
    w, h = get_image_size(img, ffprobe_path)
    r = h / w  # razão de aspecto

    strength, twist, speed, sharpen = 5, 5, 12, 30
    final_width, final_height = 1920, 1080

    A_deg = 12 * (max(0, min(100, strength)) / 100.0)
    freq = 0.2 + 1.8 * (max(0, min(100, speed)) / 100.0)
    sh = 0.30 * (max(0, min(100, twist)) / 100.0)
    amt = 1.50 * (max(0, min(100, sharpen)) / 100.0)

    A_rad = math.radians(A_deg)

    def zoom_needed(theta, aspect):
        c = abs(math.cos(theta))
        s = abs(math.sin(theta))
        return max(c + aspect * s, s + (1.0 / aspect) * c)

    # ZOOM mínimo para não aparecer borda + pequena folga
    ZOOM = zoom_needed(A_rad, r) * 1.06

    A_expr = f"({A_deg}*PI/180)"

    vf = (
        f"scale=iw*{ZOOM}:ih*{ZOOM}:flags=fast_bilinear,"          # pré-zoom
        f"shear=shx={sh}:shy=-{sh},"                               # opcional: torção leve
        f"rotate={A_expr}*sin(2*PI*{freq}*t):ow=iw:oh=ih:bilinear=0,"  # rotação senoidal (rápida)
        f"unsharp=7:7:{amt}:7:7:0,"                                # nitidez (pode remover p/ +performance)
        f"crop={final_width}:{final_height},"                      # mantém o zoom no enquadramento
        f"pad=ceil(iw/2)*2:ceil(ih/2)*2,setsar=1"
    )

    extra_enc = get_encoder_flags(encoder, framerate)

    cmd = [
        ffmpeg_path, '-y',
        '-loop', '1',
        '-t', str(segment_duration),
        '-i', os.path.abspath(img),
        '-vf', vf,
        '-r', str(framerate),
        '-c:v', encoder, *extra_enc,
        '-movflags', '+faststart',
        '-pix_fmt', 'yuv420p',
        '-threads', '0',
        '-filter_threads', '0',
        '-an',
        out_file
    ]
    return cmd


# ==========================
# Concatenação com transições (single pass)
# ==========================

def concat_with_transitions_singlepass(segment_files, audio_path, saida,
                                       segment_duration, ffmpeg_path, encoder,
                                       tipo_transicao='fade', transition=None):
    """
    Junta N segmentos com transições em UMA passada usando:
      - concat demuxer (gera [0:v])
      - trim + setpts para recortar cada bloco
      - xfade em cascata com offsets acumulados
    Requer que todos os segments tenham mesma resolução/fps/codec.
    """
    if transition is None:
        transition = min(1.0, segment_duration * 0.3)

    workdir = os.path.dirname(os.path.abspath(saida)) or '.'
    concat_list = os.path.join(workdir, 'concat_segments.txt')
    graph_path  = os.path.join(workdir, 'xfade_graph.txt')

    # 1) lista para o concat demuxer (reduz N arquivos a 1 input [0:v])
    with open(concat_list, 'w', encoding='utf-8') as f:
        for seg in segment_files:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    # 2) grafo de filtros
    n = len(segment_files)
    lines = []

    # recortes exatos de cada segmento (assumindo duração fixa por segmento)
    for i in range(n):
        start = i * segment_duration
        end   = start + segment_duration
        lines.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]")

    if n == 1:
        lines.append(f"[v0]copy[vout]")
    else:
        prev = "[v0]"
        for i in range(1, n):
            # offset acumulado = i*segment_duration - i*transition
            offset = i * segment_duration - i * transition
            lines.append(f"{prev}[v{i}]xfade=transition={tipo_transicao}:duration={transition}:offset={offset}[x{i}]")
            prev = f"[x{i}]"
        lines.append(f"{prev}copy[vout]")

    with open(graph_path, 'w', encoding='utf-8') as f:
        f.write(";\n".join(lines))

    extra_enc = get_encoder_flags(encoder, framerate=30)

    # 3) uma chamada do ffmpeg para vídeo + áudio
    cmd = [
        ffmpeg_path, '-y',
        '-f', 'concat', '-safe', '0', '-i', concat_list,  # -> [0:v]
        '-i', audio_path,                                  # -> [1:a]
        '-filter_complex_script', graph_path,
        '-map', '[vout]', '-map', '1:a',
        '-c:v', encoder, *extra_enc,
        '-c:a', 'aac',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        '-movflags', '+faststart',
        saida
    ]
    print("Executando:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # limpeza
    try:
        os.remove(concat_list)
        os.remove(graph_path)
    except Exception:
        pass


# ==========================
# Função principal
# ==========================

    # ...existing code...
