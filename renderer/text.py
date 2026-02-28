"""텍스트 렌더링 모듈 — Galmuri 픽셀 폰트로 LED 매트릭스에 선명하게 렌더링.

안티앨리어싱 없이 1비트 렌더링을 사용한다.
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Galmuri 픽셀 폰트 경로
_FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"
_FONTS = {
    "regular": _FONT_DIR / "Galmuri11.ttf",
    "bold": _FONT_DIR / "Galmuri11-Bold.ttf",
    "small": _FONT_DIR / "Galmuri9.ttf",
    "large": _FONT_DIR / "Galmuri14.ttf",
    "tiny": _FONT_DIR / "Galmuri7.ttf",
    "micro": _FONT_DIR / "Tiny5.ttf",
}

# 맑은 고딕 폴백
_FALLBACK_FONT = "C:/Windows/Fonts/malgun.ttf"
_FALLBACK_BOLD = "C:/Windows/Fonts/malgunbd.ttf"

# 폰트 캐시
_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _get_font(size: int, bold: bool = False, style: str | None = None) -> ImageFont.FreeTypeFont:
    """폰트를 로드한다 (캐싱)."""
    if style and style in _FONTS:
        path = str(_FONTS[style])
    elif bold:
        path = str(_FONTS["bold"]) if _FONTS["bold"].exists() else _FALLBACK_BOLD
    else:
        path = str(_FONTS["regular"]) if _FONTS["regular"].exists() else _FALLBACK_FONT

    key = (path, size)
    if key not in _font_cache:
        if os.path.exists(path):
            _font_cache[key] = ImageFont.truetype(path, size)
        else:
            _font_cache[key] = ImageFont.load_default(size)
    return _font_cache[key]


def render_text(
    text: str,
    font_size: int = 11,
    color: tuple = (255, 255, 255, 255),
    bold: bool = False,
    style: str | None = None,
    shadow: bool = True,
    shadow_color: tuple = (0, 0, 0, 255),
) -> Image.Image:
    """텍스트를 투명 배경의 RGBA 이미지로 렌더링한다.

    LED 매트릭스용으로 안티앨리어싱 없이 선명하게 렌더링한다.

    Args:
        style: 폰트 스타일 ("regular", "bold", "small", "large", "tiny")
    """
    font = _get_font(font_size, bold, style)
    bbox = font.getbbox(text)
    w = bbox[2] - bbox[0] + 2
    h = bbox[3] - bbox[1] + 2
    offset_x = -bbox[0] + 1
    offset_y = -bbox[1] + 1

    # 1비트 마스크로 안티앨리어싱 제거
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.fontmode = "1"
    mask_draw.text((offset_x, offset_y), text, font=font, fill=255)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    if shadow:
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow_rgba = Image.new("RGBA", (w, h), shadow_color)
        for sx, sy in [(1, 0), (0, 1), (1, 1)]:
            shadow_layer.paste(shadow_rgba, (sx, sy), mask)
        img = Image.alpha_composite(img, shadow_layer)

    text_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    text_rgba = Image.new("RGBA", (w, h), color)
    text_layer.paste(text_rgba, (0, 0), mask)
    img = Image.alpha_composite(img, text_layer)

    return img


def measure_text(text: str, font_size: int = 11, bold: bool = False, style: str | None = None) -> tuple[int, int]:
    """텍스트의 렌더링 크기(w, h)를 반환한다."""
    font = _get_font(font_size, bold, style)
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0] + 2, bbox[3] - bbox[1] + 2
