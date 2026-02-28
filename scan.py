import asyncio
from bleak import BleakScanner, BleakClient

async def scan_and_inspect():
    print("스캔 중...")
    
    # callback 방식으로 advertisement data도 함께 받기
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    
    for address, (device, adv_data) in devices.items():
        if device.name and device.name.startswith("IDM-"):
            print(f"\n발견: {device.name}")
            print(f"주소: {device.address}")
            print(f"RSSI: {adv_data.rssi} dBm")
            
            try:
                # 서비스/특성 확인
                print("\n연결 시도 중...")
                async with BleakClient(device.address) as client:
                    print("연결 성공!")
                    print("\n서비스 목록:")
                    for service in client.services:
                        print(f"  서비스: {service.uuid}")
                        for char in service.characteristics:
                            props = ", ".join(char.properties)
                            print(f"    특성: {char.uuid}")
                            print(f"      속성: {props}")
            except Exception as e:
                print(f"연결 실패: {e}")

asyncio.run(scan_and_inspect())