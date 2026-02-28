"""iDotMatrix 프로토콜 테스트 — DIY 모드 + 이미지 전송."""

import asyncio
import logging
from PIL import Image, ImageDraw
from ble.connection import scan_devices
from ble.sender import DisplaySender

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logging.getLogger("bleak").setLevel(logging.WARNING)


def create_quadrant_image() -> Image.Image:
    """4분할 색상 블록 이미지."""
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 31, 31], fill=(255, 0, 0))       # 좌상: 빨강
    draw.rectangle([32, 0, 63, 31], fill=(0, 255, 0))      # 우상: 초록
    draw.rectangle([0, 32, 31, 63], fill=(0, 0, 255))      # 좌하: 파랑
    draw.rectangle([32, 32, 63, 63], fill=(255, 255, 0))   # 우하: 노랑
    draw.line([0, 0, 63, 63], fill=(255, 255, 255), width=3)
    draw.line([63, 0, 0, 63], fill=(255, 255, 255), width=3)
    return img


async def main():
    print("=== iDotMatrix 이미지 전송 테스트 (DIY 모드) ===\n")
    devices = await scan_devices()
    if not devices:
        print("디바이스를 찾지 못했습니다.")
        return

    target = devices[0]
    print(f"대상: {target.name} ({target.address})\n")

    async with DisplaySender(target.address) as sender:
        await asyncio.sleep(1)
        await sender.set_brightness(80)
        await asyncio.sleep(0.5)

        # DIY 모드 활성화 [5, 0, 4, 1, 1]
        print("--- DIY 모드 활성화 ---")
        ok = await sender._send_command(bytes([5, 0, 4, 1, 1]))
        print(f"DIY 모드: {'성공' if ok else '실패'}")
        await asyncio.sleep(1)

        # 4분할 이미지 전송
        print("\n--- 4분할 이미지 전송 ---")
        img = create_quadrant_image()
        ok = await sender.send_image(img)
        print(f"이미지 전송: {'성공' if ok else '실패'}")

        print("\n15초간 표시 유지 (확인해주세요)...")
        await asyncio.sleep(15)

        print("완료!")


if __name__ == "__main__":
    asyncio.run(main())
