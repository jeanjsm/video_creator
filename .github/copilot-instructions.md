Copilot Instructions

Objetivo: orientar o GitHub Copilot (e humanos!) a gerar código consistente com a arquitetura do projeto Video Creator com Python e FFmpeg, mantendo separação clara entre UI, aplicação, domínio e renderização via FFmpeg.

Escopo atual do projeto (do README)

Entrada: narração (áudio) + sequência de imagens (ordem definida).

Saída: vídeo sincronizado com a narração.

Usa FFmpeg para montagem/render.

Segmenta imagens conforme segment_duration no config.json.

Suporta: overlay de vídeo, música de fundo, transições, logo.

CLI existente (ver exemplo no README).

Dependências listadas: Python 3.8+, FFmpeg (vendored em _internal/ffmpeg/bin), Flet, Vosk (futuro).

Arquitetura (alto nível)

Adotar MVVM + Pipeline FFmpeg (filtergraph) com camadas:

UI (Flet): telas, widgets e binding com ViewModels (sem regras de negócio).

Aplicação: orquestra casos de uso (abrir projeto, montar timeline, exportar).

Domínio (Core NLE): modelos puros (sem Flet/FFmpeg), validações e regras.

Render Engine: gera filtergraph a partir da timeline e executa ffmpeg.

Infra: IO, ffprobe, cache (proxies, thumbs), presets, logging, settings.

Background Workers: subprocessos para preview/geração pesada (não travar UI).

Plugins: efeitos/transições adicionáveis sem tocar no core.

Princípios: coesão alta, acoplamento baixo, domínio sem dependência de UI, side-effects nas bordas, tudo tipado (mypy).

Estrutura de pastas (sugerida)
app/
  ui/                    # Flet UI (views) — NADA de regra de negócio aqui
    views/
      main_view.py
      timeline_view.py
      inspector_view.py
    viewmodels/
      main_vm.py
      timeline_vm.py
      export_vm.py
    widgets/
      timeline_widget.py
      waveform_widget.py
  application/
    services/
      project_service.py     # abrir/salvar projeto, presets
      preview_service.py     # gerar trecho para preview
      render_service.py      # export final (progress/pause/cancel)
    commands.py              # undo/redo (Command pattern)
    use_cases/
      build_timeline_from_inputs.py
      apply_transition.py
      add_logo.py
  domain/
    models/
      project.py             # Project, Paths, Settings
      timeline.py            # Timeline, Track, Clip
      effects.py             # Effect, Transition, parameters
      audio.py               # music/ducking descriptors
    validators.py
    errors.py
  rendering/
    graph_builder.py         # Timeline -> filtergraph
    cli_builder.py           # filtergraph -> args ffmpeg (codec, bitrate, hwaccel)
    runner.py                # subprocess.Popen + -progress pipe:1
    presets/
      youtube_1080p.yaml
      reels_1080x1920.yaml
  infra/
    media_io.py              # ffprobe, streams, duration
    settings.py              # carrega config.json (pydantic-settings)
    logging.py               # logs estruturados
    cache.py                 # proxies, thumbs, waveforms
    plugins.py               # discovery/registro de plugins
    paths.py                 # resolve _internal/ffmpeg/bin
  background/
    jobs.py                  # fila + workers (multiprocessing)
    tasks/
      gen_thumb.py
      gen_proxy.py
      analyze_audio.py
      render.py
  plugins/
    builtin/
      effects/
        fade.py
        crossfade.py
        text_overlay.py
      transitions/
        fade_black.py
  main.py                    # entrypoint (CLI + inicialização Flet)
tests/
  unit/
  integration/
config.json

Convenções para o Copilot

Nunca acople Flet/FFmpeg dentro de app/domain.

Domínio usa dataclasses/pydantic, sem imports de Flet/ffmpeg/subprocess.

Assinaturas estáveis:

GraphBuilder.build(timeline: Timeline, settings: RenderSettings) -> FilterGraph

CliBuilder.make_command(graph: FilterGraph, out_path: Path, settings: RenderSettings) -> list[str]

Runner.run(cmd: list[str], on_progress: Callable[[Progress], None]) -> CompletedProcess

Progress FFmpeg: parsear -progress pipe:1 (chaves: frame, fps, bitrate, out_time_ms, speed, progress).

Undo/Redo: cada ação de edição vira um Command com do()/undo().

Plugins:

Cada efeito expõe def build_filter(self, ctx: FilterContext) -> FilterSnippet.

Registrar via infra.plugins.register_effect(EffectDescriptor).

Tipos e qualidade:

Tipagem obrigatória (from __future__ import annotations quando útil).

Linters: ruff, formatação ruff format ou black.

Testes: pytest, fixtures curtas, clipes de 1–2s para integração.

Modelos do domínio (exemplo mínimo)
# app/domain/models/timeline.py
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)
class Clip:
    id: str
    media_path: Path
    in_ms: int
    out_ms: int
    start_ms: int
    effects: list["EffectRef"] = field(default_factory=list)

@dataclass(frozen=True)
class Track:
    id: str
    kind: Literal["video", "audio"]
    clips: list[Clip] = field(default_factory=list)

@dataclass(frozen=True)
class Timeline:
    fps: Fraction
    resolution: tuple[int, int]
    video: list[Track] = field(default_factory=list)
    audio: list[Track] = field(default_factory=list)

# app/domain/models/effects.py
from dataclasses import dataclass
from typing import Literal, Mapping

@dataclass(frozen=True)
class EffectRef:
    name: str                     # ex: "fade", "xfade", "overlay", "logo"
    params: Mapping[str, str|int|float|bool]
    target: Literal["video","audio","both"] = "video"

# app/domain/models/project.py
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class RenderSettings:
    container: str         # "mp4"
    vcodec: str            # "libx264" | "h264_nvenc" | "hevc_nvenc" | "libx265"
    acodec: str            # "aac"
    crf: int               # 18-23
    preset: str            # "medium"
    audio_bitrate: str     # "192k"
    hwaccel: str | None = None  # "cuda"|"qsv"|"vaapi"|None

@dataclass
class Project:
    audio_path: Path
    image_paths: list[Path]
    overlay_path: Path | None = None
    music_path: Path | None = None
    logo_path: Path | None = None

Regras UI (Flet)

Views somente chamam ViewModels e apresentam estado; não constroem filtergraph.

Comunicação com background via asyncio + fila/thread-safe; nunca bloquear o thread da UI.

Componentes pesados (timeline, waveform) ficam em app/ui/widgets/.

Serviços de aplicação (contratos)
# app/application/services/preview_service.py
class PreviewService:
    async def render_segment_preview(self, timeline: Timeline, t0_ms: int, t1_ms: int) -> Path: ...

# app/application/services/render_service.py
class RenderService:
    def start(self, timeline: Timeline, settings: RenderSettings, output: Path) -> str: ...
    def pause(self, job_id: str) -> None: ...
    def resume(self, job_id: str) -> None: ...
    def cancel(self, job_id: str) -> None: ...

Geração de Filtergraph (padrões)

Ordem: normalizar vídeo (scale/pad → colorspace → efeitos/transições → overlays/logo → concat) e áudio (amix/adelay/volume/sidechaincompress).

Transição (crossfade): usar xfade no vídeo e acrossfade no áudio.

Logo: overlay com posição parametrizável.

Música de fundo: amix com volume relativo à narração.

Overlay de vídeo: colorkey/chromakey se necessário; respeitar FPS da timeline.

Exemplo reduzido que Copilot deve se inspirar (não colar cegamente):

filter_complex = ";".join([
  # Inputs 0:audio (narração), 1..N:imagens, M:music?, L:logo?, O:overlay?
  "[1:v]scale=iw:ih,format=yuv420p[v1]",
  "[2:v]scale=iw:ih,format=yuv420p[v2]",
  "[v1][v2]xfade=transition=fade:duration=1:offset=5[vx]",
  # Logo (se houver)
  "[vx][L:v]overlay=x=W-w-20:y=H-h-20[vout]",
  # Áudio
  "[0:a]volume=1.0[a0]",
  "[M:a]volume=0.2[abg]",
  "[a0][abg]amix=inputs=2:duration=first:dropout_transition=2[aout]",
])
cmd = [
  ffmpeg_bin, "-y",
  "-i", narration, "-i", img1, "-i", img2, "-i", music, "-i", logo,
  "-filter_complex", filter_complex,
  "-map","[vout]","-map","[aout]",
  "-c:v", vcodec, "-crf", str(crf), "-preset", preset,
  "-c:a", acodec, "-b:a", audio_bitrate,
  output
]

Regras específicas deste projeto (importante para o Copilot)

Respeitar segment_duration do config.json:

Se a soma dos segmentos < duração da narração, expandir últimas imagens proporcionalmente.

Se > duração, encurtar com prioridade aos últimos segmentos.

As imagens cobrem toda a narração automaticamente.

CLI permanece funcional: novos recursos devem expor flags coerentes (--overlay, --musica, --logo, --transicao <nome>, --preset <nome>).

FFmpeg vendorizado: resolver binário via infra.paths.ffmpeg_bin() preferencialmente a depender do PATH do SO.

Windows/macOS/Linux: não usar features específicas do SO sem fallback.

Como adicionar um efeito (roteiro para o Copilot)

Criar app/plugins/builtin/effects/<nome>.py com:

@effect(
  name="fade",
  params={"start": "float>=0", "duration": "float>0", "inout": "'in'|'out'"},
  target="video"
)
class FadeEffect(Effect):
    def build_filter(self, ctx: FilterContext) -> FilterSnippet:
        # retorna snippet tipo: "[prev]fade=t=in:st={start}:d={duration}[next]"


Registrar em infra.plugins (ou via auto-discovery).

Expor no inspector da UI (ViewModel deve validar parâmetros).

Adicionar testes:

Unit: verifica snippet esperado.

Integração curta: render 2s e checar duração + ausência de erro.

Como gerar preview sem travar a UI

PreviewService gera um trecho (ex.: 2–5s ao redor do playhead) num worker:

Usa GraphBuilder com subset da timeline.

Salva MP4 temporário (proxies em 1/2 resolução e GOP intra-frame).

UI apenas toca o arquivo temporário em componente de vídeo do Flet (ou bridge para mpv).

Observabilidade e erros

Logar comando completo do FFmpeg e stderr quando exit code != 0.

Converter linhas de -progress em evento Progress(percent, time_ms, speed).

Mensagens para UI amigáveis; detalhes técnicos nos logs.

Presets (render)

YAML em app/rendering/presets/.
Campos: container, vcodec, acodec, crf, preset, audio_bitrate, hwaccel (opcional), resolution, fps (se quiser forçar).

render_service.start(..., settings=load_preset("youtube_1080p")).

Testes mínimos que o Copilot deve gerar

Unit:

GraphBuilder monta filtergraph esperado para: sem transição, com crossfade, com logo, com música.

Normalização de segment_duration vs. duração da narração.

Integração (rápidos):

Render 3 imagens + 1 narração curta (1–2s) → saída tem aprox. mesma duração ± 100ms.

Render com --musica e volume reduzido → amix presente no comando.

Smoke:

CLI com parâmetros obrigatórios retorna código 0 e cria arquivo.

O que não fazer

Não colocar subprocess.Popen dentro de ViewModels/Views.

Não manipular paths do FFmpeg diretamente na UI (use infra.paths).

Não acessar config.json em domain (somente via infra.settings).

Não bloquear a thread da UI (render, thumbs, proxies sempre em background).

Snippets que o Copilot pode usar (com placeholders)
# Carregar config.json
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    segment_duration: float = 3.0
    class Config:
        env_prefix = "APP_"
        env_file = ".env"

settings = AppSettings(_secrets_dir=".")

# Progresso
@dataclass(frozen=True)
class Progress:
    out_time_ms: int
    speed: float | None
    percent: float | None

def parse_progress_line(line: str) -> dict[str,str]: ...

# Descobrir ffmpeg/ffprobe na pasta interna
def ffmpeg_bin() -> str:
    base = Path(__file__).resolve().parents[2] / "_internal" / "ffmpeg" / "bin"
    return str(base / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))

# CLI (trecho)
import argparse
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--audio", required=True)
    p.add_argument("--imagens", nargs="+", required=True)
    p.add_argument("--saida", required=True)
    p.add_argument("--overlay")
    p.add_argument("--musica")
    p.add_argument("--logo")
    p.add_argument("--transicao", default="none")
    p.add_argument("--preset", default="youtube_1080p")
    return p

Prompt de “intenção” para o Copilot

Quando eu criar/editar código neste repositório:

Siga a estrutura de pastas e as camadas descritas.

Gere dataclasses tipadas no domínio; não importe Flet/FFmpeg no domínio.

Para renderização, sempre: Timeline -> FilterGraph (GraphBuilder) -> list[str] (CliBuilder) -> Runner.

Use -progress pipe:1 e publique progresso como eventos.

Respeite segment_duration do config.json para cobrir toda a narração com as imagens.

Exponha novas capacidades na CLI e prepare pontos de extensão em plugins/.

Escreva testes unitários e um teste de integração curto ao criar novos efeitos/transições.

Evite blocos longos em UI; delegue a serviços de aplicação.

Roadmap curto (para orientar sugestões do Copilot)

MVP UI (Flet): importar mídia, configurar preset, botão “Exportar”.

Preview por trecho + geração de proxies.

Transições (fade/crossfade) e logo com posição configurável.

Música de fundo com ducking simples.

Autosave do projeto + presets em YAML.

Packaging (PyInstaller onedir) incluindo FFmpeg vendorizado.


O mais importante é garantir que a arquitetura esteja bem definida e que cada componente tenha responsabilidades claras. Isso facilitará a manutenção e a evolução do sistema ao longo do tempo.
Não hesite em refatorar e melhorar o código à medida que avança.
Nunca comprometa a qualidade do código em nome da velocidade. É melhor fazer as coisas corretamente da primeira vez.
Nunca adicione código desnecessário ou redundante.
Nunca escreva código que não seja testável.
Nunca deixe código quebrado.
