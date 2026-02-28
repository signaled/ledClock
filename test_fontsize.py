"""혼합 폰트 테스트 — 한글=Galmuri9, 숫자/영문/기호=Galmuri7."""

import asyncio
import logging
import unicodedata
from PIL import Image, ImageDraw, ImageFont
from ble.connection import scan_devices
from ble.sender import DisplaySender
from renderer.layers import LayerCompositor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("bleak").setLevel(logging.WARNING)

FONT_KO = ImageFont.truetype("assets/fonts/Galmuri9.ttf", 9)
FONT_EN = ImageFont.truetype("assets/fonts/Galmuri7.ttf", 7)

TEXT = "02/14 (금) 3°"


def is_korean(ch):
    """한글 여부 판별."""
    cp = ord(ch)
    # 한글 음절, 자모, 호환 자모
    return (0xAC00 <= cp <= 0xD7AF or
            0x1100 <= cp <= 0x11FF or
            0x3130 <= cp <= 0x318F)


def render_mixed(text, font_ko, font_en, color=(255, 255, 255, 255)):
    """한글은 font_ko, 나머지는 font_en으로 글자별 렌더링 후 합성."""
    # 각 글자의 이미지와 baseline 정보 수집
    char_imgs = []
    max_ascent = 0
    max_descent = 0

    for ch in text:
        font = font_ko if is_korean(ch) else font_en
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
        char_imgs.append((mask, ascent, w, h, is_korean(ch)))

    # 전체 이미지 크기
    total_w = sum(ci[2] for ci in char_imgs) + 1
    total_h = max_ascent + max_descent + 1

    img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    x = 0
    for mask, ascent, w, h, korean in char_imgs:
        y = max_ascent - ascent
        if korean:
            y -= 2  # 한글 2px 위로
        colored = Image.new("RGBA", (w, h), color)
        img.paste(colored, (x, max(0, y)), mask)
        x += w

    return img


async def main():
    devices = await scan_devices()
    if not devices:
        return

    bg = Image.new("RGB", (64, 64), (10, 5, 25))
    compositor = LayerCompositor()

    # 혼합 렌더링
    mixed = render_mixed(TEXT, FONT_KO, FONT_EN)
    # 비교용: Galmuri7 only
    only7 = render_mixed(TEXT, FONT_EN, FONT_EN)
    # 비교용: Galmuri9 only
    only9 = render_mixed(TEXT, FONT_KO, FONT_KO)

    label_font = ImageFont.truetype("assets/fonts/Galmuri7.ttf", 7)

    def make_label(text, color=(255, 255, 0, 255)):
        bbox = label_font.getbbox(text)
        w = bbox[2] - bbox[0] + 2
        h = bbox[3] - bbox[1] + 2
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        d.fontmode = "1"
        d.text((-bbox[0]+1, -bbox[1]+1), text, font=label_font, fill=255)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer = Image.new("RGBA", (w, h), color)
        img.paste(layer, (0, 0), mask)
        return img

    lbl_mix = make_label("Mix 9+7")
    lbl_7 = make_label("Galmuri7")
    lbl_9 = make_label("Galmuri9")

    print(f"  Mix: {mixed.width}x{mixed.height}")
    print(f"  G7:  {only7.width}x{only7.height}")
    print(f"  G9:  {only9.width}x{only9.height}")

    overlays = [
        (lbl_mix, (1, 1)),
        (mixed, (1, 10)),
        (lbl_7, (1, 23)),
        (only7, (1, 32)),
        (lbl_9, (1, 45)),
        (only9, (1, 54)),
    ]

    frame = compositor.compose(background=bg, overlays=overlays)

    async with DisplaySender(devices[0].address) as sender:
        await asyncio.sleep(1)
        await sender.set_brightness(80)
        await sender.send_image(frame)
        print("표시 중... 15초 후 종료")
        await asyncio.sleep(15)
        print("완료!")


if __name__ == "__main__":
    asyncio.run(main())
