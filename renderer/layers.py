"""레이어 합성 모듈 — 배경 + 텍스트 오버레이."""

from PIL import Image
from .canvas import Canvas, WIDTH, HEIGHT


class LayerCompositor:
    """배경과 텍스트 레이어를 합성하여 최종 프레임을 생성한다."""

    def __init__(self):
        self._canvas = Canvas()

    def compose(
        self,
        background: Image.Image | None = None,
        overlays: list[tuple[Image.Image, tuple[int, int]]] | None = None,
    ) -> Image.Image:
        """배경 위에 오버레이 레이어들을 합성하여 RGB 이미지를 반환한다.

        Args:
            background: 64x64 배경 이미지 (None이면 검정 배경)
            overlays: [(이미지, (x, y))] 형태의 오버레이 리스트

        Returns:
            64x64 RGB 이미지 (BLE 전송용)
        """
        self._canvas.clear()

        # 배경 레이어
        if background is not None:
            bg = background.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
            self._canvas.paste(bg)

        # 오버레이 레이어들
        if overlays:
            for layer_img, position in overlays:
                self._canvas.paste(layer_img, position)

        return self._canvas.to_rgb()
