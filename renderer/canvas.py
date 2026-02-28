"""64x64 Pillow 캔버스 관리 모듈."""

from PIL import Image

# 디스플레이 크기
WIDTH = 64
HEIGHT = 64


class Canvas:
    """64x64 RGBA 캔버스."""

    def __init__(self):
        self._image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))

    @property
    def image(self) -> Image.Image:
        return self._image

    def clear(self, color: tuple = (0, 0, 0, 255)) -> None:
        """캔버스를 지정 색상으로 초기화한다."""
        self._image = Image.new("RGBA", (WIDTH, HEIGHT), color)

    def paste(self, layer: Image.Image, position: tuple = (0, 0)) -> None:
        """레이어를 캔버스 위에 합성한다 (알파 블렌딩)."""
        if layer.mode != "RGBA":
            layer = layer.convert("RGBA")
        self._image = Image.alpha_composite(self._image, _place(layer, position))

    def to_rgb(self) -> Image.Image:
        """RGB 모드로 변환하여 반환한다 (BLE 전송용)."""
        return self._image.convert("RGB")


def _place(layer: Image.Image, position: tuple) -> Image.Image:
    """레이어를 64x64 캔버스 크기에 맞춰 지정 위치에 배치한다."""
    if layer.size == (WIDTH, HEIGHT) and position == (0, 0):
        return layer
    result = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    result.paste(layer, position)
    return result
