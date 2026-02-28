"""렌더링 테스트 — 혼합 폰트, 그림자, 풍경 배경."""

import asyncio
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from ble.connection import scan_devices
from ble.sender import DisplaySender
from renderer.text import render_text
from renderer.layers import LayerCompositor
from content.weather_icons import get_weather_icon

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("bleak").setLevel(logging.WARNING)

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_COLORS = {
    0: (255, 255, 255, 255),
    1: (255, 255, 255, 255),
    2: (255, 255, 255, 255),
    3: (255, 255, 255, 255),
    4: (255, 255, 255, 255),
    5: (80, 130, 255, 255),
    6: (255, 80, 80, 255),
}

FONT_KO = ImageFont.truetype("assets/fonts/Galmuri9.ttf", 9)
FONT_EN = ImageFont.truetype("assets/fonts/Galmuri7.ttf", 7)
SCREEN_W = 64
SCREEN_H = 64


def is_korean(ch):
    cp = ord(ch)
    return (0xAC00 <= cp <= 0xD7AF or
            0x1100 <= cp <= 0x11FF or
            0x3130 <= cp <= 0x318F)


def render_mixed(text, color=(255, 255, 255, 255), kerning=-1,
                 shadow=True, shadow_color=(0, 0, 0, 255)):
    """한글=Galmuri9, 나머지=Galmuri7 혼합 렌더링. alpha_composite로 그림자."""
    char_imgs = []
    max_ascent = 0
    max_descent = 0

    for ch in text:
        korean = is_korean(ch)
        font = FONT_KO if korean else FONT_EN
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

    # 그림자 레이어 (3방향: 오른쪽, 아래, 대각선)
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


def add_shadow(icon: Image.Image, shadow_color=(0, 0, 0, 255)) -> Image.Image:
    """아이콘에 3방향 1px 그림자 추가."""
    w, h = icon.size
    result = Image.new("RGBA", (w + 1, h + 1), (0, 0, 0, 0))
    alpha = icon.split()[3]
    shadow = Image.new("RGBA", (w, h), shadow_color)
    shadow_layer = Image.new("RGBA", (w + 1, h + 1), (0, 0, 0, 0))
    for sx, sy in [(1, 0), (0, 1), (1, 1)]:
        shadow_layer.paste(shadow, (sx, sy), alpha)
    result = Image.alpha_composite(result, shadow_layer)
    # 본문
    icon_layer = Image.new("RGBA", (w + 1, h + 1), (0, 0, 0, 0))
    icon_layer.paste(icon, (0, 0), icon)
    result = Image.alpha_composite(result, icon_layer)
    return result


def create_gradient_bg() -> Image.Image:
    """단순 그라데이션 배경."""
    img = Image.new("RGB", (SCREEN_W, SCREEN_H))
    draw = ImageDraw.Draw(img)
    for y in range(SCREEN_H):
        r = int(10 + y * 0.4)
        g = int(5 + y * 0.2)
        b = int(40 + y * 0.6)
        draw.line([(0, y), (63, y)], fill=(r, g, b))
    return img


def create_landscape_bg() -> Image.Image:
    """픽셀 풍경 배경 (하늘+산+잔디)."""
    img = Image.new("RGB", (SCREEN_W, SCREEN_H))
    draw = ImageDraw.Draw(img)

    # 하늘 그라데이션
    for y in range(40):
        r = int(20 + y * 1.5)
        g = int(10 + y * 1.0)
        b = int(80 + y * 2.0)
        draw.line([(0, y), (63, y)], fill=(r, g, b))

    # 산 (뒤쪽, 어두운 보라)
    mountain1 = [
        (0, 45), (8, 30), (16, 35), (24, 25), (32, 32),
        (40, 28), (48, 34), (56, 30), (63, 38), (63, 45), (0, 45)
    ]
    draw.polygon(mountain1, fill=(40, 30, 60))

    # 산 (앞쪽, 짙은 녹색)
    mountain2 = [
        (0, 50), (10, 38), (20, 42), (30, 35), (40, 40),
        (50, 36), (58, 42), (63, 45), (63, 50), (0, 50)
    ]
    draw.polygon(mountain2, fill=(25, 50, 35))

    # 잔디/땅
    for y in range(50, 64):
        g = int(40 + (y - 50) * 2)
        draw.line([(0, y), (63, y)], fill=(15, g, 10))

    # 별 (텍스트 영역 y<30 피해서 배치)
    stars = [(5, 31), (15, 33), (30, 30), (45, 32), (55, 34), (60, 31), (38, 35)]
    for sx, sy in stars:
        draw.point((sx, sy), fill=(200, 200, 255))

    return img


def format_time_ampm(now: datetime) -> str:
    hour = now.hour
    ampm = "AM" if hour < 12 else "PM"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    return f"{ampm} {display_hour:02d}:{now.minute:02d}"


async def main():
    print("=== 풍경 배경 + 그림자 테스트 ===\n")
    devices = await scan_devices()
    if not devices:
        return

    compositor = LayerCompositor()
    bg = create_gradient_bg()

    async with DisplaySender(devices[0].address) as sender:
        await asyncio.sleep(1)
        await sender.set_brightness(80)

        print("10초마다 시간 갱신 (Ctrl+C로 종료)\n")
        count = 0
        while True:
            count += 1
            now = datetime.now()
            time_str = format_time_ampm(now)
            date_str = now.strftime("%m/%d")
            weekday_idx = now.weekday()
            weekday_name = WEEKDAY_NAMES[weekday_idx]
            weekday_color = WEEKDAY_COLORS[weekday_idx]

            # AM/PM (regular) + 시간 (bold) 분리 렌더링
            ampm = "AM" if now.hour < 12 else "PM"
            display_hour = now.hour % 12
            if display_hour == 0:
                display_hour = 12
            clock_str = f"{display_hour:02d}:{now.minute:02d}"
            ampm_img = render_text(ampm + " ", font_size=9, style="small")
            clock_img = render_text(clock_str, font_size=12, bold=True)

            # 날짜+요일 혼합 폰트 (그림자 포함)
            date_full = f"{date_str} {weekday_name}"
            date_img = render_mixed(date_full, color=weekday_color)

            # 날씨 아이콘 + 그림자
            weather_icon = add_shadow(get_weather_icon("sunny"))
            temp_img = render_text("3°", font_size=11, color=(255, 200, 100, 255))

            # 날짜: 오른쪽 정렬
            date_x = SCREEN_W - date_img.width - 1

            # 날씨: 오른쪽 아래
            icon_x = SCREEN_W - weather_icon.width - temp_img.width - 4
            icon_y = SCREEN_H - weather_icon.height - 2
            temp_x = icon_x + weather_icon.width + 2
            temp_y = icon_y + 2

            clock_x = 2 + ampm_img.width
            frame = compositor.compose(
                background=bg,
                overlays=[
                    (ampm_img, (2, 2)),
                    (clock_img, (clock_x, 2)),
                    (date_img, (date_x, 18)),
                    (weather_icon, (icon_x, icon_y)),
                    (temp_img, (temp_x, temp_y)),
                ],
            )

            ok = await sender.send_image(frame)
            print(f"[{count}] {time_str} {date_full} → {'OK' if ok else 'FAIL'}")

            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
