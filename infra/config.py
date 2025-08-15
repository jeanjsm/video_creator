
"""
infra/config.py — Infraestrutura (Clean Architecture)
----------------------------------------------------
Responsável por acesso a recursos externos (config.json, disco, etc).
Não contém lógica de negócio, apenas utilitários de infraestrutura.
"""
import os
import json

def get_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}
