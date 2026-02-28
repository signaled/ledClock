"""IDM 디바이스에 raw BLE 명령을 보내 프로토콜 호환성을 확인하는 스크립트."""

import asyncio
import logging
from bleak import BleakClient, BleakScanner

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(name)s] %(message)s")

WRITE_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"

# AE 서비스 (IDM 전용?)
AE_WRITE_UUID = "0000ae01-0000-1000-8000-00805f9b34fb"
AE_NOTIFY_UUID = "0000ae02-0000-1000-8000-00805f9b34fb"

received_data = []


def on_notify(sender, data):
    """FA03 notify 콜백."""
    print(f"  [FA03 응답] {data.hex()} (길이={len(data)})")
    received_data.append(("FA03", data))


def on_ae_notify(sender, data):
    """AE02 notify 콜백."""
    print(f"  [AE02 응답] {data.hex()} (길이={len(data)})")
    received_data.append(("AE02", data))


async def main():
    # 스캔
    print("=== 디바이스 스캔 ===")
    devices = await BleakScanner.discover(timeout=10.0)
    target = None
    for d in devices:
        if d.name and d.name.startswith("IDM-"):
            target = d
            print(f"발견: {d.name} ({d.address})")
            break

    if not target:
        print("IDM 디바이스를 찾지 못했습니다.")
        return

    print(f"\n=== {target.name} 연결 ===")
    async with BleakClient(target.address) as client:
        print("연결 성공!")

        # notify 구독
        await client.start_notify(NOTIFY_UUID, on_notify)
        await client.start_notify(AE_NOTIFY_UUID, on_ae_notify)
        await asyncio.sleep(0.5)

        # 1) pypixelcolor의 get_device_info 명령
        from datetime import datetime
        now = datetime.now()
        cmd_info = bytes([8, 0, 1, 0x80, now.hour, now.minute, now.second, 0])
        print(f"\n--- [1] device_info 명령 (FA02): {cmd_info.hex()} ---")
        await client.write_gatt_char(WRITE_UUID, cmd_info, response=True)
        await asyncio.sleep(3)

        # 2) 밝기 설정 명령
        cmd_brightness = bytes([5, 0, 4, 0x80, 30])
        print(f"\n--- [2] 밝기 30 명령 (FA02): {cmd_brightness.hex()} ---")
        await client.write_gatt_char(WRITE_UUID, cmd_brightness, response=True)
        await asyncio.sleep(2)

        # 3) AE01로도 device_info 전송 시도
        print(f"\n--- [3] device_info 명령 (AE01): {cmd_info.hex()} ---")
        await client.write_gatt_char(AE_WRITE_UUID, cmd_info)
        await asyncio.sleep(3)

        await client.stop_notify(NOTIFY_UUID)
        await client.stop_notify(AE_NOTIFY_UUID)

    print(f"\n=== 수신된 응답 총 {len(received_data)}건 ===")
    for src, data in received_data:
        print(f"  [{src}] {data.hex()} ({list(data)})")


if __name__ == "__main__":
    asyncio.run(main())
