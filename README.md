# Video Creator com Python e FFmpeg

Este projeto é um aplicativo em Python para criar vídeos automaticamente a partir de um arquivo de narração (áudio) e uma sequência de imagens, utilizando o FFmpeg.

## O que o projeto já faz

- Recebe um arquivo de áudio (narração)
- Recebe uma lista de imagens (em ordem)
- Gera um vídeo sincronizando as imagens com a narração
- Utiliza FFmpeg para montagem e renderização do vídeo
- Segmenta as imagens conforme a duração definida em `segment_duration` no config.json
- Permite adicionar overlay de vídeo (ex: animações, chroma key, etc)
- Permite adicionar música de fundo
- Permite adicionar transições entre imagens
- Permite adicionar logo sobre o vídeo
- As imagens cobrem toda a narração automaticamente

## Exemplo de uso (CLI)
```bash
python main.py --audio narracao.mp3 --imagens img1.jpg img2.jpg img3.jpg --saida video_final.mp4 --overlay overlay.mp4 --musica fundo.mp3 --logo logo.png
```

## Pré-requisitos
- Python 3.8+
- FFmpeg (já incluso na pasta `_internal/ffmpeg/bin/`)
- Bibliotecas Python: 
    - Flet
    - Vosk

## Como usar (exemplo futuro)
```bash
python main.py --audio narracao.mp3 --imagens img1.jpg img2.jpg img3.jpg --saida video_final.mp4
```

## Estrutura inicial do projeto
- `main.py` — Script principal
- `config.json` — Configurações do projeto
- `_internal/ffmpeg/` — Binários e documentação do FFmpeg


## Próximos passos
- Integração com reconhecimento de fala (Vosk)
- Interface gráfica (Flet)
- Testes automatizados mais abrangentes

## Arquitetura
- MVVM + Pipeline FFmpeg


---

Sinta-se à vontade para sugerir melhorias ou funcionalidades!


