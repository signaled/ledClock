"""확실히 구분되는 이미지 전송 테스트."""

import asyncio
import logging
from PIL import Image, ImageDraw
from ble.connection import scan_devices
from ble.sender import DisplaySender

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logging.getLogger("bleak").setLevel(logging.WARNING)


def create_quadrant_image() -> Image.Image:
    """4분할 색상 블록 + 대각선 — 확실히 구분 가능한 이미지."""
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 4분할: 빨강 / 초록 / 파랑 / 노랑
    draw.rectangle([0, 0, 31, 31], fill=(255, 0, 0))       # 좌상: 빨강
    draw.rectangle([32, 0, 63, 31], fill=(0, 255, 0))      # 우상: 초록
    draw.rectangle([0, 32, 31, 63], fill=(0, 0, 255))      # 좌하: 파랑
    draw.rectangle([32, 32, 63, 63], fill=(255, 255, 0))   # 우하: 노랑

    # 중앙에 흰색 X 표시
    draw.line([0, 0, 63, 63], fill=(255, 255, 255), width=2)
    draw.line([63, 0, 0, 63], fill=(255, 255, 255), width=2)

    # 테두리
    draw.rectangle([0, 0, 63, 63], outline=(255, 255, 255))

    return img


async def main():
    print("=== 4분할 이미지 전송 테스트 ===")
    devices = await scan_devices()
    if not devices:
        print("디바이스를 찾지 못했습니다.")
        return

    target = devices[0]
    print(f"대상: {target.name} ({target.address})")

    img = create_quadrant_image()
    print("4분할 이미지 생성 (좌상:빨강, 우상:초록, 좌하:파랑, 우하:노랑, 대각선:흰색)")

    async with DisplaySender(target.address) as sender:
        await asyncio.sleep(1)

        # 밝기 최대
        await sender.set_brightness(100)
        await asyncio.sleep(0.5)

        # 이미지 전송
        ok = await sender.send_image(img)
        print(f"\n이미지 전송: {'성공' if ok else '실패'}")

        if ok:
            print("10초간 표시 유지...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
