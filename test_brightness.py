"""밝기 제어 테스트 — 다른 이미지 표시 + 밝기 최대→최소→최대."""

import asyncio
import logging
import math
from PIL import Image, ImageDraw
from ble.connection import scan_devices
from ble.sender import DisplaySender

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("bleak").setLevel(logging.WARNING)


def create_test_image() -> Image.Image:
    """무지개 원형 패턴 이미지 생성."""
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = 32, 32

    for y in range(64):
        for x in range(64):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy)
            angle = math.atan2(dy, dx)

            # 거리 기반 밝기 (중심이 밝음)
            brightness = max(0, 1.0 - dist / 36)

            # 각도 기반 색상 (무지개)
            hue = (angle + math.pi) / (2 * math.pi)  # 0~1
            r, g, b = _hsv_to_rgb(hue, 1.0, brightness)
            draw.point((x, y), fill=(int(r * 255), int(g * 255), int(b * 255)))

    # 중앙에 흰색 하트 모양
    heart_points = []
    for t_i in range(100):
        t = t_i / 100 * 2 * math.pi
        hx = 16 * math.sin(t) ** 3
        hy = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
        px = int(cx + hx * 0.5)
        py = int(cy + hy * 0.5 - 2)
        if 0 <= px < 64 and 0 <= py < 64:
            draw.point((px, py), fill=(255, 255, 255))

    return img


def _hsv_to_rgb(h, s, v):
    """HSV → RGB 변환."""
    if s == 0:
        return v, v, v
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    i %= 6
    if i == 0: return v, t, p
    if i == 1: return q, v, p
    if i == 2: return p, v, t
    if i == 3: return p, q, v
    if i == 4: return t, p, v
    return v, p, q


async def main():
    print("=== BLE 디바이스 스캔 ===")
    devices = await scan_devices()
    if not devices:
        print("디바이스를 찾지 못했습니다.")
        return

    target = devices[0]
    print(f"대상: {target.name} ({target.address})")

    # 무지개 원형 이미지 생성
    img = create_test_image()
    print("무지개 원형 패턴 이미지 생성 완료")

    async with DisplaySender(target.address) as sender:
        await asyncio.sleep(1)

        # 이미지 전송
        ok = await sender.send_image(img)
        print(f"이미지 전송: {'성공' if ok else '실패'}")
        if not ok:
            return

        await asyncio.sleep(2)

        # 밝기 100 → 0 (최대에서 최소로)
        print("\n--- 밝기: 100 → 0 ---")
        for level in range(100, -1, -10):
            ok = await sender.set_brightness(level)
            print(f"  밝기 {level:3d}: {'OK' if ok else 'FAIL'}")
            await asyncio.sleep(0.5)

        await asyncio.sleep(1)

        # 밝기 0 → 100 (최소에서 최대로)
        print("\n--- 밝기: 0 → 100 ---")
        for level in range(0, 101, 10):
            ok = await sender.set_brightness(level)
            print(f"  밝기 {level:3d}: {'OK' if ok else 'FAIL'}")
            await asyncio.sleep(0.5)

        print("\n완료! 3초 후 종료합니다.")
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
