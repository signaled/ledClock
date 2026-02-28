"""메인 루프 — BLE LED 픽셀 디스플레이 통합 실행."""

import asyncio
import logging
import time
from datetime import datetime

from PIL import Image

from config import load_config
from ble.connection import scan_devices
from ble.sender import DisplaySender
from renderer.text import render_text
from renderer.layers import LayerCompositor
from renderer.layout import Layout
from content.clock import ClockContent
from content.weather import create_weather_provider, WeatherData
from content.weather_icons import get_weather_icon
from content.background import BackgroundManager, DynamicBackground
from scheduler import Scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("bleak").setLevel(logging.WARNING)


async def main():
    config = load_config()

    # 모듈 초기화
    clock = ClockContent()
    weather_prov = create_weather_provider(config["weather"])
    bg_mgr = BackgroundManager(
        bg_dir=config["background"].get("directory", "assets/backgrounds/"),
        brightness=1.0,
    )
    dynamic_bg = DynamicBackground()
    compositor = LayerCompositor()
    layout = Layout()
    scheduler = Scheduler(
        weather_interval_min=config["weather"].get("update_interval_min", 30),
        bg_interval_min=config["background"].get("rotation_interval_min", 10),
    )

    # 배경 로드
    bg_count = bg_mgr.load_all()
    logging.info("배경 %d개 로드됨", bg_count)

    # BLE 디바이스 검색
    logging.info("BLE 디바이스 검색 중...")
    devices = await scan_devices(
        name_prefix=config["ble"].get("device_name_prefix", "IDM-"),
    )
    if not devices:
        logging.error("디바이스를 찾지 못했습니다.")
        return

    # 초기 데이터
    weather = await weather_prov.get_weather()
    bg = bg_mgr.get_current()

    async with DisplaySender(
        devices[0].address,
        reconnect_interval=config["ble"].get("reconnect_interval_sec", 10),
    ) as sender:
        await asyncio.sleep(1)
        brightness = config["display"].get("brightness", 50)
        await sender.set_brightness(brightness)

        logging.info("디스플레이 시작 (밝기: %d)", brightness)

        target_fps = config["display"].get("fps", 1)
        frame_interval = 1.0 / target_fps
        last_second = -1

        # 변하지 않는 요소 캐시
        cached_icon = None
        cached_temp_img = None
        cached_date_img = None
        cached_condition = None

        while True:
            frame_start = time.time()
            now = datetime.now()
            cur_second = now.second
            show_colon = cur_second % 2 == 0

            # 날씨 갱신 체크 (30분 간격)
            if scheduler.should_update_weather():
                weather = await weather_prov.get_weather()
                cached_condition = None  # 캐시 무효화

            # 배경 전환 체크
            if scheduler.should_update_background():
                bg = bg_mgr.next()

            # 배경 프레임: 파일 배경이 있으면 그것 사용, 없으면 동적 배경
            if bg_mgr.has_backgrounds():
                bg_frame = bg_mgr.get_frame()
            else:
                bg_frame = dynamic_bg.get_frame(
                    now.hour, now.minute, weather.condition,
                )

            # 매초 1회만 갱신하는 요소
            if cur_second != last_second:
                ampm_img = clock.render_ampm(now)
                time_img = clock.render_time(now, show_colon=show_colon)
                last_second = cur_second

                # 날짜는 분 단위로 변경되므로 매초 갱신해도 무방
                cached_date_img = clock.render_date(now)

            # 날씨 아이콘/온도 캐시
            if cached_condition != weather.condition:
                cached_condition = weather.condition
                cached_icon = get_weather_icon(weather.condition)
                cur_img = render_text(f"{weather.temp:.0f}° ", font_size=8, style="tiny", color=(255, 200, 100, 255))
                mm_img = render_text(f"{weather.temp_min:.0f}°/{weather.temp_max:.0f}°", font_size=8, style="tiny", color=(190, 190, 200, 255))
                cached_temp_img = Image.new("RGBA", (cur_img.width + mm_img.width, max(cur_img.height, mm_img.height)), (0, 0, 0, 0))
                cached_temp_img.paste(cur_img, (0, 0), cur_img)
                cached_temp_img.paste(mm_img, (cur_img.width, 0), mm_img)

            # 레이아웃 배치
            overlays = layout.compose(
                background=bg_frame,
                ampm=ampm_img,
                time=time_img,
                date=cached_date_img,
                weather_icon=cached_icon,
                temp=cached_temp_img,
            )

            # 합성 및 전송
            frame = compositor.compose(background=bg_frame, overlays=overlays)
            await sender.send_image(frame)

            # 프레임 간격 유지
            elapsed = time.time() - frame_start
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("종료")
