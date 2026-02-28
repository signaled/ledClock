"""BLE 디바이스 스캔·연결·재연결 관리 모듈."""

import asyncio
import logging
from bleak import BleakScanner

logger = logging.getLogger(__name__)


async def scan_devices(name_prefix: str = "IDM-", timeout: float = 10.0) -> list:
    """BLE 디바이스를 스캔하여 이름 접두사가 일치하는 디바이스 목록을 반환한다.

    LED_BLE_ 접두사도 함께 검색한다.
    """
    logger.info("BLE 디바이스 스캔 중... (timeout=%ss)", timeout)
    devices = await BleakScanner.discover(timeout=timeout)

    prefixes = (name_prefix, "LED_BLE_")
    found = [
        d for d in devices
        if d.name and any(d.name.startswith(p) for p in prefixes)
    ]

    for d in found:
        logger.info("발견: %s (%s)", d.name, d.address)

    if not found:
        logger.warning("일치하는 디바이스를 찾지 못했습니다.")

    return found
