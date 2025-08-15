# Config loader for video_creator
import json
import os


def get_config():
    # Caminho correto considerando a estrutura: app/infra/config.py -> ../../config.json
    config_path = os.path.join(os.path.dirname(__file__), "../..", "config.json")
    config_path = os.path.abspath(config_path)

    if not os.path.exists(config_path):
        print(f"DEBUG: config.json não encontrado em: {config_path}")
        return {}

    with open(config_path, encoding="utf-8") as f:
        return json.load(f)
