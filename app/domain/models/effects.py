# -*- coding: utf-8 -*-
"""
Modelos de efeitos e transições para o domínio
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Mapping, Any, Protocol


@dataclass(frozen=True)
class EffectDescriptor:
    """Descritor de um efeito disponível no sistema"""

    name: str
    params: Mapping[str, str]  # nome_param: tipo_validacao
    target: Literal["video", "audio", "both"]
    description: str = ""


class FilterContext:
    """Contexto para construção de filtros FFmpeg"""

    def __init__(self, input_label: str, output_label: str, **kwargs):
        self.input_label = input_label
        self.output_label = output_label
        self.params = kwargs


class FilterSnippet:
    """Representa um fragmento de filtro FFmpeg"""

    def __init__(self, filter_expr: str):
        self.filter_expr = filter_expr


class Effect(Protocol):
    """Interface para implementação de efeitos"""

    def build_filter(self, ctx: FilterContext) -> FilterSnippet:
        """Constrói o filtro FFmpeg para este efeito"""
        ...


@dataclass(frozen=True)
class Transition:
    """Representa uma transição entre clipes"""

    name: str
    duration_ms: int
    params: Mapping[str, Any] = None
