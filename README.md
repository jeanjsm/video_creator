# Video Creator com Python e FFmpeg

Este projeto é um aplicativo em Python para criar vídeos automaticamente a partir de um arquivo de narração (áudio) e uma sequência de imagens, utilizando o FFmpeg.

## Status Atual

- **Arquitetura Clean Architecture/MVVM**: O projeto está em transição para uma arquitetura desacoplada, com separação clara entre UI (Flet), aplicação, domínio e renderização (GraphBuilder → CliBuilder → Runner).
- **Pipeline Moderno**: O fluxo principal já utiliza as camadas:
    - Timeline (domínio) → FilterGraph (GraphBuilder) → Comando FFmpeg (CliBuilder) → Execução (Runner)
- **CLI funcional**: Suporta todos os recursos principais via linha de comando.
- **Overlay com chroma key**: Implementado, com suporte a múltiplos overlays, opacidade, posição e duração na timeline.
- **Transições e efeitos**: Suporte a transições (fade, smoothleft, circleopen, etc) e efeitos visuais nas imagens.
- **Logo e capa**: Inserção de logo e capa com controle de posição, opacidade e escala.
- **Música de fundo**: Mixagem automática com controle de volume.
- **Segmentação automática**: As imagens são distribuídas para cobrir toda a narração, respeitando o `segment_duration` do `config.json`.
- **FFmpeg vendorizado**: Não depende do FFmpeg do sistema, usa binários internos.
- **Logs detalhados**: Toda execução é registrada em `debug_video_creator.log` para depuração.

## Em desenvolvimento

- **Refatoração completa para Clean Architecture**: Algumas rotas ainda usam lógicas legadas, mas a migração está avançada.
- **Plugins de efeitos/transições**: Estrutura pronta para plugins, com exemplos de efeitos e transições.
- **Preview e geração de proxies**: Em andamento para não travar a UI.
- **Testes automatizados**: Testes unitários e de integração estão sendo expandidos.
- **Interface gráfica (Flet)**: MVP em construção.

## Exemplo de uso (CLI)

```bash
python main.py --audio narracao.mp3 --saida video_final.mp4 --logo logo.png --capa capa.png --musica_fundo fundo.mp3 --transicao fade
```

Veja todos os parâmetros com `python main.py --help`.

## Estrutura do projeto

- `main.py` — Entrypoint CLI
- `config.json` — Configurações globais
- `_internal/ffmpeg/` — Binários do FFmpeg
- `app/` — Código principal, dividido em:
    - `ui/` (Flet, views/viewmodels/widgets)
    - `application/` (serviços, comandos, use_cases)
    - `domain/` (modelos, validações)
    - `rendering/` (GraphBuilder, CliBuilder, Runner, presets)
    - `infra/` (IO, settings, logging, cache, plugins)
    - `background/` (workers, tasks)
    - `plugins/` (efeitos/transições)
- `tests/` — Testes unitários e integração

## Próximos passos

- Finalizar refatoração para Clean Architecture
- MVP da interface gráfica (Flet)
- Preview rápido e geração de proxies
- Plugins de efeitos/transições customizados
- Integração com reconhecimento de fala (Vosk)
- Testes automatizados mais abrangentes

---

Sinta-se à vontade para sugerir melhorias ou funcionalidades!


