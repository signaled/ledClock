"""이미지 전송 시간 측정."""

import asyncio
import time
import logging
from PIL import Image, ImageDraw
from ble.connection import scan_devices
from ble.sender import DisplaySender
from renderer.text import render_text
from renderer.layers import LayerCompositor
from datetime import datetime
from io import BytesIO

logging.basicConfig(level=logging.WARNING)


async def main():
    devices = await scan_devices()
    if not devices:
        return

    compositor = LayerCompositor()

    # 배경 생성
    bg = Image.new("RGB", (64, 64))
    draw = ImageDraw.Draw(bg)
    for y in range(64):
        draw.line([(0, y), (63, y)], fill=(int(10 + y * 0.4), int(5 + y * 0.2), int(40 + y * 0.6)))

    async with DisplaySender(devices[0].address) as sender:
        await asyncio.sleep(1)
        await sender.set_brightness(80)

        print("=== 전송 시간 측정 (10회) ===\n")
        times = []

        for i in range(10):
            now = datetime.now()
            time_img = render_text(now.strftime("%H:%M:%S"), font_size=14, bold=True)
            date_img = render_text(now.strftime("%m/%d") + f" ({['월','화','수','목','금','토','일'][now.weekday()]})", font_size=10)
            label_img = render_text("오늘 날씨: 맑음", font_size=10, color=(200, 200, 255, 255))

            # 렌더링 시간 측정
            t0 = time.perf_counter()
            frame = compositor.compose(background=bg, overlays=[
                (time_img, (2, 4)),
                (date_img, (2, 22)),
                (label_img, (2, 50)),
            ])
            t_render = time.perf_counter() - t0

            # PNG 변환 시간
            t1 = time.perf_counter()
            rgb = frame.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
            buf = BytesIO()
            rgb.save(buf, format="PNG")
            png_size = len(buf.getvalue())
            t_png = time.perf_counter() - t1

            # BLE 전송 시간
            t2 = time.perf_counter()
            ok = await sender.send_image(frame)
            t_ble = time.perf_counter() - t2

            t_total = t_render + t_png + t_ble
            times.append(t_ble)

            print(f"[{i+1:2d}] 렌더링: {t_render*1000:5.1f}ms | PNG({png_size}B): {t_png*1000:5.1f}ms | BLE전송: {t_ble*1000:5.1f}ms | 합계: {t_total*1000:5.1f}ms")

            await asyncio.sleep(0.5)

        avg = sum(times) / len(times) * 1000
        print(f"\nBLE 전송 평균: {avg:.1f}ms")


if __name__ == "__main__":
    asyncio.run(main())
