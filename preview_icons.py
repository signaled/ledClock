"""날씨 아이콘 PC 미리보기 — 확대된 PNG 파일로 저장 후 열기."""

from PIL import Image, ImageDraw, ImageFont
from content.weather_icons import get_weather_icon, WEATHER_ICONS

SCALE = 8   # 38x38 → 304x304
PADDING = 16
LABEL_HEIGHT = 30

ICONS = ["sunny", "partly_cloudy", "cloudy", "rain", "snow", "thunder"]
LABELS = ["Sunny", "Partly Cloudy", "Cloudy", "Rain", "Snow", "Thunder"]


def preview():
    icon_size = 39 * SCALE  # 38+1(shadow) scaled
    cell_w = icon_size + PADDING * 2
    cell_h = icon_size + PADDING * 2 + LABEL_HEIGHT

    cols = len(ICONS)
    width = cell_w * cols
    height = cell_h

    canvas = Image.new("RGB", (width, height), (30, 30, 40))
    draw = ImageDraw.Draw(canvas)

    for i, (condition, label) in enumerate(zip(ICONS, LABELS)):
        icon = get_weather_icon(condition, shadow=True)
        # NEAREST로 확대 (픽셀 아트 유지)
        scaled = icon.resize(
            (icon.width * SCALE, icon.height * SCALE),
            Image.NEAREST,
        )
        x = i * cell_w + PADDING
        y = PADDING
        canvas.paste(scaled, (x, y), scaled)

        # 라벨
        lx = i * cell_w + cell_w // 2
        ly = y + icon_size + 4
        draw.text((lx, ly), label, fill=(200, 200, 200), anchor="mt")

    out = "preview_icons.png"
    canvas.save(out)
    print(f"저장됨: {out} ({width}x{height})")

    # 전체 프레임 미리보기도 생성
    _preview_frame(canvas)

    import os
    os.startfile(out)


def _preview_frame(icons_canvas):
    """실제 64x64 화면 구성을 확대해서 미리보기."""
    from content.clock import ClockContent
    from renderer.text import render_text
    from renderer.layers import LayerCompositor
    from content.background import BackgroundManager
    from datetime import datetime

    SCREEN_W, SCREEN_H = 64, 64

    clock = ClockContent()
    compositor = LayerCompositor()
    bg = BackgroundManager.default_gradient()

    now = datetime.now()
    ampm_img = clock.render_ampm(now)
    time_img = clock.render_time(now)
    date_img = clock.render_date(now)
    from renderer.layout import Layout
    layout = Layout()

    icon = get_weather_icon("sunny")
    cur_img = render_text("5° ", font_size=7, style="tiny", color=(255, 200, 100, 255))
    mm_img = render_text("2°/11°", font_size=7, style="tiny", color=(190, 190, 200, 255))
    temp_img = Image.new("RGBA", (cur_img.width + mm_img.width, max(cur_img.height, mm_img.height)), (0, 0, 0, 0))
    temp_img.paste(cur_img, (0, 0), cur_img)
    temp_img.paste(mm_img, (cur_img.width, 0), mm_img)

    overlays = layout.compose(
        background=bg,
        ampm=ampm_img,
        time=time_img,
        date=date_img,
        weather_icon=icon,
        temp=temp_img,
    )
    frame = compositor.compose(background=bg, overlays=overlays)

    # 10배 확대
    scaled = frame.resize((640, 640), Image.NEAREST)
    out = "preview_frame.png"
    scaled.save(out)
    print(f"전체 프레임 저장됨: {out} (640x640)")


if __name__ == "__main__":
    preview()
