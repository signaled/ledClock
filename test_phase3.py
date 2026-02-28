"""Phase 3 통합 테스트 — 모듈화된 clock/weather/background 사용."""

import asyncio
import logging
from datetime import datetime
from PIL import Image
from ble.connection import scan_devices
from ble.sender import DisplaySender
from renderer.text import render_text
from renderer.layers import LayerCompositor
from content.clock import ClockContent
from content.weather import WeatherProvider
from content.weather_icons import get_weather_icon
from content.background import BackgroundManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("bleak").setLevel(logging.WARNING)

SCREEN_W = 64
SCREEN_H = 64


async def main():
    print("=== Phase 3 통합 테스트 ===\n")
    devices = await scan_devices()
    if not devices:
        return

    clock = ClockContent()
    weather_prov = WeatherProvider()
    bg_mgr = BackgroundManager()
    compositor = LayerCompositor()

    bg = bg_mgr.get_current()
    weather = await weather_prov.get_weather()

    async with DisplaySender(devices[0].address) as sender:
        await asyncio.sleep(1)
        await sender.set_brightness(80)

        print("1초마다 갱신, 콜론 깜빡임 (Ctrl+C로 종료)\n")
        count = 0
        while True:
            count += 1
            now = datetime.now()
            show_colon = now.second % 2 == 0

            # 시간
            ampm_img = clock.render_ampm(now)
            time_img = clock.render_time(now, show_colon=show_colon)
            clock_x = 2 + ampm_img.width

            # 날짜
            date_img = clock.render_date(now)
            date_x = SCREEN_W - date_img.width - 1

            # 날씨 아이콘 + 온도
            icon = get_weather_icon(weather.condition)
            temp_str = f"{weather.temp:.0f}°"
            temp_img = render_text(temp_str, font_size=11, color=(255, 200, 100, 255))

            icon_x = SCREEN_W - icon.width - temp_img.width - 4
            icon_y = SCREEN_H - icon.height - 2
            temp_x = icon_x + icon.width + 2
            temp_y = icon_y + 2

            frame = compositor.compose(
                background=bg,
                overlays=[
                    (ampm_img, (2, 2)),
                    (time_img, (clock_x, 2)),
                    (date_img, (date_x, 18)),
                    (icon, (icon_x, icon_y)),
                    (temp_img, (temp_x, temp_y)),
                ],
            )

            ok = await sender.send_image(frame)
            print(f"[{count}] {now.strftime('%H:%M:%S')} → {'OK' if ok else 'FAIL'}")

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
