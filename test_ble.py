"""BLE 연결 및 테스트 이미지 전송 스크립트."""

import asyncio
import logging
from PIL import Image, ImageDraw
from ble.connection import scan_devices
from ble.sender import DisplaySender

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
# bleak 로그는 INFO로 제한
logging.getLogger("bleak").setLevel(logging.INFO)


async def main():
    # 1단계: 디바이스 스캔
    print("=== BLE 디바이스 스캔 ===")
    devices = await scan_devices()

    if not devices:
        print("디바이스를 찾지 못했습니다. 종료합니다.")
        return

    target = devices[0]
    print(f"\n대상 디바이스: {target.name} ({target.address})")

    # 2단계: 테스트 이미지 생성 (64x64 빨강/파랑 그라데이션)
    print("\n=== 테스트 이미지 생성 ===")
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(64):
        for x in range(64):
            r = int(x * 255 / 63)
            b = int(y * 255 / 63)
            draw.point((x, y), fill=(r, 0, b))

    # PNG 크기 확인
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    print(f"64x64 테스트 이미지 PNG 크기: {len(buf.getvalue())} 바이트")

    # 3단계: 연결 및 전송
    print("\n=== BLE 연결 및 전송 ===")
    async with DisplaySender(target.address) as sender:
        await asyncio.sleep(1)  # 연결 안정화 대기

        # 밝기 설정
        ok = await sender.set_brightness(30)
        print(f"밝기 30 설정: {'성공' if ok else '실패'}")
        await asyncio.sleep(1)

        # 테스트 이미지 전송
        print("\n이미지 전송 시작...")
        ok = await sender.send_image(img)
        print(f"테스트 이미지 전송: {'성공' if ok else '실패'}")

        if ok:
            print("\n5초 대기 후 종료...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
