from typing import Mapping


class ChromaOverlayEffect:
    """Classe para encapsular o efeito de overlay chroma key (vídeo com chromakey e ducking de áudio)."""

    def __init__(self, params: Mapping[str, str | int | float | bool]):
        self.path = params.get("path")
        self.start = float(params.get("start", 0.0))
        self.margin = int(params.get("margin", 0))
        self.duration = params.get("duration")  # pode ser None
        self.colorkey = params.get("colorkey", "0x00FF00")
        self.colorkey_similarity = float(params.get("colorkey_similarity", 0.35))
        self.colorkey_blend = float(params.get("colorkey_blend", 0.10))
        self.threshold = float(params.get("threshold", 0.03))
        self.ratio = float(params.get("ratio", 8))
        self.attack = int(params.get("attack", 5))
        self.release = int(params.get("release", 300))
        # Novos campos para position e size
        self.position = params.get("position", "bottom_right")
        self.size = float(params.get("size", 1.0))

    def build_filter(
        self,
        main_video_label: str,
        overlay_label: str,
        main_audio_label: str = None,
        overlay_audio_label: str = None,
        v_out: str = "v",
        a_out: str = "aout",
    ) -> str:
        # Expressão enable
        if self.duration:
            enable_expr = (
                f":enable='between(t,{self.start},{self.start + float(self.duration)})'"
            )
        else:
            enable_expr = ""

        # Mapeamento de posição
        pos_map = {
            "top_left": ("20", "20"),
            "top_center": ("(main_w-overlay_w)/2", "20"),
            "top_right": ("main_w-overlay_w-20", "20"),
            "center_left": ("20", "(main_h-overlay_h)/2"),
            "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
            "center_right": ("main_w-overlay_w-20", "(main_h-overlay_h)/2"),
            "bottom_left": ("20", "main_h-overlay_h-20"),
            "bottom_center": ("(main_w-overlay_w)/2", "main_h-overlay_h-20"),
            "bottom_right": ("main_w-overlay_w-20", "main_h-overlay_h-20"),
        }
        x_expr, y_expr = pos_map.get(
            self.position, ("main_w-overlay_w-40", "main_h-overlay_h-40")
        )

        # Corrigir size (escala)
        scale_expr = f"iw*{self.size}:ih*{self.size}"

        # VIDEO
        video_chain = (
            f"[{overlay_label}]setpts=PTS+{self.start}/TB,"
            f"colorkey={self.colorkey}:{self.colorkey_similarity}:{self.colorkey_blend},"
            f"scale={scale_expr}[ck];"
            f"[{main_video_label}][ck]overlay=x='{x_expr}':y='{y_expr}'{enable_expr}[{v_out}]"
        )
        if main_audio_label and overlay_audio_label and a_out:
            adelay_ms = int(self.start * 1000)
            audio_chain = (
                f"[{overlay_audio_label}]adelay={adelay_ms}|{adelay_ms},apad[a1];"
                f"[{main_audio_label}][a1]sidechaincompress=threshold={self.threshold}:ratio={self.ratio}:attack={self.attack}:release={self.release}[mixduck];"
                f"[mixduck][a1]amix=inputs=2:duration=longest:dropout_transition=250[{a_out}]"
            )
            return video_chain + ";" + audio_chain
        else:
            return video_chain
