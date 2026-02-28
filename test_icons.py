"""날씨 아이콘 전체 확인 — 5초마다 아이콘 변경."""

import asyncio
import logging
from datetime import datetime
from ble.connection import scan_devices
from ble.sender import DisplaySender
from renderer.text import render_text
from renderer.layers import LayerCompositor
from content.clock import ClockContent
from content.weather_icons import get_weather_icon
from content.background import BackgroundManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("bleak").setLevel(logging.WARNING)

ICONS = ["sunny", "partly_cloudy", "cloudy", "rain", "snow", "thunder"]
ICON_LABELS = ["Sunny", "Partly", "Cloudy", "Rain", "Snow", "Thunder"]
SCREEN_W = 64
SCREEN_H = 64


async def main():
    devices = await scan_devices()
    if not devices:
        return

    clock = ClockContent()
    compositor = LayerCompositor()
    bg = BackgroundManager.default_gradient()

    async with DisplaySender(devices[0].address) as sender:
        await asyncio.sleep(1)
        await sender.set_brightness(80)

        for i, (condition, label) in enumerate(zip(ICONS, ICON_LABELS)):
            now = datetime.now()
            ampm_img = clock.render_ampm(now)
            time_img = clock.render_time(now)
            date_img = clock.render_date(now)

            icon = get_weather_icon(condition)
            label_img = render_text(label, font_size=7, style="tiny", color=(200, 200, 255, 255))
            temp_img = render_text("3°", font_size=11, color=(255, 200, 100, 255))

            clock_x = 2 + ampm_img.width
            date_x = SCREEN_W - date_img.width - 1
            icon_x = SCREEN_W - icon.width - temp_img.width - 4
            icon_y = SCREEN_H - icon.height - 2
            temp_x = icon_x + icon.width + 2
            temp_y = icon_y + 2
            label_x = SCREEN_W - label_img.width - 1
            label_y = icon_y - label_img.height - 1

            frame = compositor.compose(background=bg, overlays=[
                (ampm_img, (2, 2)),
                (time_img, (clock_x, 2)),
                (date_img, (date_x, 18)),
                (label_img, (label_x, label_y)),
                (icon, (icon_x, icon_y)),
                (temp_img, (temp_x, temp_y)),
            ])

            await sender.send_image(frame)
            print(f"[{i+1}/7] {label} ({condition})")
            await asyncio.sleep(5)

        print("완료!")


if __name__ == "__main__":
    asyncio.run(main())
