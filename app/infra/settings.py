# -*- coding: utf-8 -*-
"""
Settings management using pydantic-settings
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class AppSettings(BaseSettings):
    """Configurações da aplicação"""

    segment_duration: float = 3.0
    image_source_dir: str = ""
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None

    class Config:
        env_prefix = "APP_"
        env_file = ".env"
        case_sensitive = False


def load_settings() -> AppSettings:
    """Carrega as configurações da aplicação"""
    # Primeiro tenta carregar do config.json (compatibilidade)
    config_path = Path("config.json")
    if config_path.exists():
        import json

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        return AppSettings(**config_data)

    # Senão carrega das variáveis de ambiente ou padrões
    return AppSettings()


# Instância global das configurações
settings = load_settings()
