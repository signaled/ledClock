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

# 시스템 폴백 폰트 (OS별)
import sys as _sys

def _find_fallback(bold: bool = False) -> str:
    """OS에 맞는 폴백 폰트 경로를 반환한다."""
    candidates = []
    if _sys.platform == "win32":
        candidates = ["C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf"]
    elif _sys.platform == "darwin":
        candidates = ["/System/Library/Fonts/AppleSDGothicNeo.ttc"]
    else:
        # Linux / Raspberry Pi
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""

_FALLBACK_FONT = _find_fallback(bold=False)
_FALLBACK_BOLD = _find_fallback(bold=True)

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
    monospace: bool = False,
) -> Image.Image:
    """텍스트를 투명 배경의 RGBA 이미지로 렌더링한다.

    LED 매트릭스용으로 안티앨리어싱 없이 선명하게 렌더링한다.

    Args:
        style: 폰트 스타일 ("regular", "bold", "small", "large", "tiny")
        monospace: True면 모든 문자를 동일 폭 셀에 중앙 배치
    """
    font = _get_font(font_size, bold, style)

    if monospace:
        return _render_monospace(text, font, color, shadow, shadow_color)

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


def _render_monospace(
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple,
    shadow: bool,
    shadow_color: tuple,
) -> Image.Image:
    """숫자만 동일 폭 셀에 중앙 배치, 나머지는 원래 폭으로 렌더링한다."""
    # 숫자 중 가장 넓은 글자 기준으로 셀 폭 결정
    digit_w = 0
    min_top = 999
    max_bottom = 0
    glyphs = []
    for ch in text:
        bbox = font.getbbox(ch)
        gw = bbox[2] - bbox[0]
        gh = bbox[3] - bbox[1]
        is_digit = ch.isdigit()
        if is_digit and gw > digit_w:
            digit_w = gw
        if bbox[1] < min_top:
            min_top = bbox[1]
        if bbox[3] > max_bottom:
            max_bottom = bbox[3]
        glyphs.append((ch, bbox, gw, gh, is_digit))

    digit_cell = digit_w + 1  # 숫자 셀 폭 (여백 포함)
    # 전체 폭 계산: 숫자는 고정폭, 나머지는 원래 폭 + 1
    total_w = 0
    for ch, bbox, gw, gh, is_digit in glyphs:
        total_w += digit_cell if is_digit else gw + 1

    total_h = max_bottom - min_top + 2
    sw = total_w + (1 if shadow else 0)
    sh = total_h + (1 if shadow else 0)
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))

    x = 0
    for ch, bbox, gw, gh, is_digit in glyphs:
        if is_digit:
            cx = x + (digit_cell - gw) // 2  # 셀 내 중앙
            advance = digit_cell
        else:
            cx = x
            advance = gw + 1

        # 공통 기준선 기반 y 좌표
        cy = bbox[1] - min_top + 1

        mask = Image.new("L", (gw + 1, gh + 1), 0)
        d = ImageDraw.Draw(mask)
        d.fontmode = "1"
        d.text((-bbox[0], -bbox[1]), ch, font=font, fill=255)

        if shadow:
            sc = Image.new("RGBA", mask.size, shadow_color)
            for sx, sy in [(1, 0), (0, 1), (1, 1)]:
                img.paste(sc, (cx + sx, cy + sy), mask)

        cc = Image.new("RGBA", mask.size, color)
        img.paste(cc, (cx, cy), mask)
        x += advance

    return img


def measure_text(text: str, font_size: int = 11, bold: bool = False, style: str | None = None) -> tuple[int, int]:
    """텍스트의 렌더링 크기(w, h)를 반환한다."""
    font = _get_font(font_size, bold, style)
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0] + 2, bbox[3] - bbox[1] + 2
