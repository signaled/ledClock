"""날짜/시간 콘텐츠 모듈 — 시간·날짜 텍스트 이미지를 생성한다."""

from datetime import datetime
from PIL import Image, ImageFont, ImageDraw

from renderer.text import render_text

# 요일 영문 약어
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# 요일 색상: 평일=흰, 토=파랑, 일=빨강
WEEKDAY_COLORS = {
    0: (255, 255, 255, 255),  # Mon
    1: (255, 255, 255, 255),  # Tue
    2: (255, 255, 255, 255),  # Wed
    3: (255, 255, 255, 255),  # Thu
    4: (255, 255, 255, 255),  # Fri
    5: (80, 130, 255, 255),   # Sat: 파랑
    6: (255, 80, 80, 255),    # Sun: 빨강
}

# 혼합 폰트 (날짜용: 한글=Galmuri9, 영문/숫자=Galmuri7)
_FONT_KO = None
_FONT_EN = None


def _load_fonts():
    global _FONT_KO, _FONT_EN
    if _FONT_KO is None:
        from pathlib import Path
        font_dir = Path(__file__).parent.parent / "assets" / "fonts"
        _FONT_KO = ImageFont.truetype(str(font_dir / "Galmuri9.ttf"), 9)
        _FONT_EN = ImageFont.truetype(str(font_dir / "Galmuri7.ttf"), 7)


def _is_korean(ch: str) -> bool:
    cp = ord(ch)
    return (0xAC00 <= cp <= 0xD7AF or
            0x1100 <= cp <= 0x11FF or
            0x3130 <= cp <= 0x318F)


def render_mixed(text: str, color=(255, 255, 255, 255), kerning=-1,
                 shadow=True, shadow_color=(0, 0, 0, 255)) -> Image.Image:
    """한글=Galmuri9, 영문/숫자=Galmuri7 혼합 렌더링. 한글 2px 위로."""
    _load_fonts()
    char_imgs = []
    max_ascent = 0
    max_descent = 0

    for ch in text:
        korean = _is_korean(ch)
        font = _FONT_KO if korean else _FONT_EN
        bbox = font.getbbox(ch)
        w = bbox[2] - bbox[0] + 1
        h = bbox[3] - bbox[1] + 1
        ascent = -bbox[1]
        descent = bbox[3]
        if ascent > max_ascent:
            max_ascent = ascent
        if descent > max_descent:
            max_descent = descent

        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        d.fontmode = "1"
        d.text((-bbox[0], -bbox[1]), ch, font=font, fill=255)
        char_imgs.append((ch, mask, ascent, w, h, korean))

    total_h = max_ascent + max_descent + 1
    num_gaps = max(0, len(char_imgs) - 1)
    total_w = sum(ci[3] for ci in char_imgs) + num_gaps * kerning + 1

    sw = max(1, total_w) + (1 if shadow else 0)
    sh = total_h + (1 if shadow else 0)
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))

    # 그림자 레이어 (3방향)
    if shadow:
        shadow_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        for sx, sy in [(1, 0), (0, 1), (1, 1)]:
            x = 0
            for i, (ch, mask, ascent, w, h, korean) in enumerate(char_imgs):
                if i > 0:
                    x += kerning
                y = max_ascent - ascent
                if korean:
                    y -= 2
                sc = Image.new("RGBA", (w, h), shadow_color)
                shadow_layer.paste(sc, (x + sx, max(0, y) + sy), mask)
                x += w
        img = Image.alpha_composite(img, shadow_layer)

    # 본문 레이어
    text_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    x = 0
    for i, (ch, mask, ascent, w, h, korean) in enumerate(char_imgs):
        if i > 0:
            x += kerning
        y = max_ascent - ascent
        if korean:
            y -= 2
        colored = Image.new("RGBA", (w, h), color)
        text_layer.paste(colored, (x, max(0, y)), mask)
        x += w
    img = Image.alpha_composite(img, text_layer)

    return img


class ClockContent:
    """시간·날짜 콘텐츠를 생성한다."""

    def render_ampm(self, now: datetime) -> Image.Image:
        """AM/PM 텍스트 이미지 (Galmuri9, 9px)."""
        ampm = "AM" if now.hour < 12 else "PM"
        return render_text(ampm + " ", font_size=9, style="small")

    def render_time(self, now: datetime, show_colon: bool = True) -> Image.Image:
        """시간 텍스트 이미지 (Galmuri11-Bold, 12px). show_colon=False면 콜론 숨김."""
        hour = now.hour % 12
        if hour == 0:
            hour = 12
        sep = ":" if show_colon else " "
        return render_text(f"{hour:02d}{sep}{now.minute:02d}", font_size=12, bold=True)

    def render_date(self, now: datetime) -> Image.Image:
        """날짜+요일 텍스트 이미지 (혼합 폰트, 요일 색상 적용)."""
        date_str = now.strftime("%m/%d")
        weekday_idx = now.weekday()
        weekday_name = WEEKDAY_NAMES[weekday_idx]
        color = WEEKDAY_COLORS[weekday_idx]
        return render_mixed(f"{date_str} {weekday_name}", color=color)

    def get_weekday_color(self, now: datetime) -> tuple:
        """현재 요일의 색상을 반환한다."""
        return WEEKDAY_COLORS[now.weekday()]
