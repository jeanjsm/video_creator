# -*- coding: utf-8 -*-
"""
Plugin system for effects and transitions
"""

from typing import Dict, Type, List
from ..domain.models.effects import Effect, EffectDescriptor


class PluginRegistry:
    """Registry para plugins de efeitos"""

    def __init__(self):
        self._effects: Dict[str, Type[Effect]] = {}
        self._descriptors: Dict[str, EffectDescriptor] = {}

    def register_effect(self, descriptor: EffectDescriptor, effect_class: Type[Effect]):
        """Registra um novo efeito"""
        self._effects[descriptor.name] = effect_class
        self._descriptors[descriptor.name] = descriptor

    def get_effect(self, name: str) -> Type[Effect] | None:
        """Obtém uma classe de efeito pelo nome"""
        return self._effects.get(name)

    def get_descriptor(self, name: str) -> EffectDescriptor | None:
        """Obtém o descritor de um efeito"""
        return self._descriptors.get(name)

    def list_effects(self) -> List[EffectDescriptor]:
        """Lista todos os efeitos registrados"""
        return list(self._descriptors.values())


# Instância global do registry
plugin_registry = PluginRegistry()


def effect(name: str, params: Dict[str, str], target: str, description: str = ""):
    """Decorator para registrar efeitos"""

    def decorator(effect_class: Type[Effect]):
        descriptor = EffectDescriptor(
            name=name, params=params, target=target, description=description
        )
        plugin_registry.register_effect(descriptor, effect_class)
        return effect_class

    return decorator
