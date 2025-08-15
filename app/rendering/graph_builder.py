# -*- coding: utf-8 -*-
"""
Construção de filtergraph FFmpeg a partir da timeline
"""

from ..domain.models.timeline import Timeline
from ..domain.models.effects import FilterContext, FilterSnippet
from ..infra.plugins import plugin_registry
from typing import List


class FilterGraph:
    """Representa um filtergraph FFmpeg"""

    def __init__(self):
        self.filters: List[str] = []
        self.inputs: List[str] = []
        self.outputs: List[str] = []

    def add_filter(self, filter_expr: str):
        """Adiciona um filtro ao graph"""
        self.filters.append(filter_expr)

    def to_string(self) -> str:
        """Converte o filtergraph para string FFmpeg"""
        return ";".join(self.filters)


class GraphBuilder:
    """Constrói filtergraph a partir de timeline"""

    def build(self, timeline: Timeline, settings=None) -> FilterGraph:
        """Constrói o filtergraph para a timeline"""
        graph = FilterGraph()

        # Implementação básica - seria expandida conforme necessário
        # Por enquanto, apenas concatena os vídeos das tracks

        video_inputs = []
        for track in timeline.video:
            for clip in track.clips:
                # Adiciona input para cada clipe
                input_label = f"v{len(video_inputs)}"
                video_inputs.append(input_label)

                # Aplica efeitos do clipe
                current_label = input_label
                for effect_ref in clip.effects:
                    effect_class = plugin_registry.get_effect(effect_ref.name)
                    if effect_class:
                        effect = effect_class()
                        next_label = f"{current_label}_fx"
                        ctx = FilterContext(
                            current_label, next_label, **effect_ref.params
                        )
                        snippet = effect.build_filter(ctx)
                        graph.add_filter(snippet.filter_expr)
                        current_label = next_label

        # Concatena os vídeos se houver múltiplos
        if len(video_inputs) > 1:
            concat_inputs = "".join(f"[{inp}]" for inp in video_inputs)
            graph.add_filter(
                f"{concat_inputs}concat=n={len(video_inputs)}:v=1:a=0[vout]"
            )
        elif len(video_inputs) == 1:
            graph.add_filter(f"[{video_inputs[0]}]copy[vout]")

        return graph
