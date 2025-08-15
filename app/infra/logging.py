# -*- coding: utf-8 -*-
"""
Logging configuration for the application
"""

import logging
import sys
from pathlib import Path


def setup_logging(log_file: str = "video_creator.log", level: int = logging.INFO):
    """Configura o sistema de logging"""

    # Formato dos logs
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Handler para arquivo
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)  # Só warnings e erros no console

    # Configuração do logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Obtém um logger com o nome especificado"""
    return logging.getLogger(name)
