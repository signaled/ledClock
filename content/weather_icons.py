"""날씨 아이콘 모듈 — Material Symbols 16x16 렌더링."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# 아이콘 크기
ICON_SIZE = 38

# Material Symbols 폰트
_FONT_PATH = Path(__file__).parent.parent / "assets" / "fonts" / "MaterialSymbols.ttf"
_font: ImageFont.FreeTypeFont | None = None

# Bootstrap Icons 폰트
_BI_FONT_PATH = Path(__file__).parent.parent / "assets" / "fonts" / "bootstrap-icons.woff"
_bi_font: ImageFont.FreeTypeFont | None = None


def _get_font() -> ImageFont.FreeTypeFont:
    global _font
    if _font is None:
        _font = ImageFont.truetype(str(_FONT_PATH), ICON_SIZE)
    return _font


def _get_bi_font() -> ImageFont.FreeTypeFont:
    global _bi_font
    if _bi_font is None:
        _bi_font = ImageFont.truetype(str(_BI_FONT_PATH), ICON_SIZE)
    return _bi_font


# Material Symbols 코드포인트
_ICON_CHARS = {
    "thunder": "\uec1c",        # electric_bolt
}

# Bootstrap Icons 코드포인트
_BI_ICON_CHARS = {
    "sunny": chr(62882),        # sun
    "partly_cloudy": chr(62142),  # cloud-sun
    "cloudy": chr(62147),       # clouds
    "rain": chr(62973),         # umbrella
    "snow": chr(62830),         # snow2
}

# 아이콘별 색상
_ICON_COLORS = {
    "sunny": (255, 220, 50, 255),
    "partly_cloudy": (120, 120, 140, 255),
    "cloudy": (100, 100, 120, 255),
    "rain": (130, 170, 255, 255),
    "snow": (120, 130, 150, 255),
    "thunder": (255, 230, 100, 255),
}


def _render_icon(condition: str) -> Image.Image:
    """아이콘을 RGBA로 렌더링 (폰트 자동 선택)."""
    if condition in _ICON_CHARS:
        font = _get_font()
        char = _ICON_CHARS[condition]
    else:
        font = _get_bi_font()
        char = _BI_ICON_CHARS.get(condition, _BI_ICON_CHARS["sunny"])

    color = _ICON_COLORS.get(condition, (220, 220, 240, 255))

    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bbox = font.getbbox(char)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (ICON_SIZE - w) // 2 - bbox[0]
    y = (ICON_SIZE - h) // 2 - bbox[1]
    draw.text((x, y), char, fill=color, font=font)

    return img


# 날씨 코드 → 아이콘 매핑 (기존 인터페이스 유지)
WEATHER_ICONS = {
    "sunny": lambda: _render_icon("sunny"),
    "cloudy": lambda: _render_icon("cloudy"),
    "partly_cloudy": lambda: _render_icon("partly_cloudy"),
    "rain": lambda: _render_icon("rain"),
    "snow": lambda: _render_icon("snow"),
    "thunder": lambda: _render_icon("thunder"),
}


def get_weather_icon(condition: str, shadow: bool = True) -> Image.Image:
    """날씨 조건 문자열로 아이콘을 반환한다."""
    factory = WEATHER_ICONS.get(condition, WEATHER_ICONS["sunny"])
    icon = factory()
    if shadow:
        icon = _add_shadow(icon)
    return icon


def _add_shadow(icon: Image.Image, shadow_color=(0, 0, 0, 255)) -> Image.Image:
    """아이콘에 3방향 1px 그림자 추가."""
    w, h = icon.size
    result = Image.new("RGBA", (w + 1, h + 1), (0, 0, 0, 0))
    alpha = icon.split()[3]
    shadow = Image.new("RGBA", (w, h), shadow_color)
    shadow_layer = Image.new("RGBA", (w + 1, h + 1), (0, 0, 0, 0))
    for sx, sy in [(1, 0), (0, 1), (1, 1)]:
        shadow_layer.paste(shadow, (sx, sy), alpha)
    result = Image.alpha_composite(result, shadow_layer)
    icon_layer = Image.new("RGBA", (w + 1, h + 1), (0, 0, 0, 0))
    icon_layer.paste(icon, (0, 0), icon)
    result = Image.alpha_composite(result, icon_layer)
    return result
