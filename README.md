# Video Creator com Python e FFmpeg

Este projeto é um aplicativo em Python para criar vídeos automaticamente a partir de um arquivo de narração (áudio) e uma sequência de imagens, utilizando o FFmpeg.

## Funcionalidades previstas
- Receber um arquivo de áudio (narração)
- Receber uma lista de imagens (em ordem)
- Gerar um vídeo sincronizando as imagens com a narração
- Utilizar FFmpeg para montagem e renderização do vídeo
- As imagens devem cobrir toda a narração
- A duração das imagens no vídeo está no arquivo de configuração: segment_duration

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
1. Definir dependências e estrutura dos scripts
2. Implementar leitura dos argumentos e arquivos
3. Integrar chamada ao FFmpeg
4. Gerar vídeo de exemplo

## Arquitetura
- Clean Architecture


---

Sinta-se à vontade para sugerir melhorias ou funcionalidades!
