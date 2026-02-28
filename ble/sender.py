"""iDotMatrix BLE LED 디스플레이 전송 모듈.

iDotMatrix (IDM-) 디바이스 전용 프로토콜 구현.
참조: https://github.com/derkalle4/python3-idotmatrix-library
"""

import asyncio
import logging
import struct
import zlib
from io import BytesIO
from pathlib import Path

from bleak import BleakClient
from PIL import Image

logger = logging.getLogger(__name__)

WRITE_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"

IMAGE_CHUNK_SIZE = 4096  # iDotMatrix 이미지 청크 크기
ACK_TIMEOUT = 8.0


class DisplaySender:
    """iDotMatrix LED 디스플레이에 이미지를 전송하는 클래스."""

    def __init__(self, address: str, reconnect_interval: int = 10):
        self._address = address
        self._reconnect_interval = reconnect_interval
        self._client: BleakClient | None = None
        self._connected = False
        self._mtu_size: int = 20  # 기본값, 연결 시 갱신
        self._diy_mode_active = False
        # ACK 이벤트
        self._chunk_ack = asyncio.Event()
        self._final_ack = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._connected

    def _on_disconnect(self, client):
        logger.warning("BLE 연결 끊김: %s", self._address)
        self._connected = False

    def _on_notify(self, sender, data: bytes):
        """FA03 notify 콜백 — ACK 처리."""
        if not data:
            return
        logger.debug("Notify: %s", data.hex())
        # iDotMatrix ACK: 5바이트, data[0]==0x05
        if len(data) >= 5 and data[0] == 0x05:
            code = data[4]
            if code in (0, 1, 2):
                self._chunk_ack.set()
            if code == 3:
                self._chunk_ack.set()
                self._final_ack.set()

    async def connect(self) -> None:
        """디바이스에 연결하고 notify를 구독한다."""
        logger.info("BLE 연결 시도: %s", self._address)
        self._client = BleakClient(
            self._address, disconnected_callback=self._on_disconnect
        )
        await self._client.connect()
        # MTU 크기 확인 — characteristic의 max_write_without_response_size 사용 (크로스플랫폼)
        try:
            char = self._client.services.get_characteristic(WRITE_UUID)
            if char and char.max_write_without_response_size > 20:
                self._mtu_size = char.max_write_without_response_size
            else:
                self._mtu_size = self._client.mtu_size - 3
        except Exception:
            self._mtu_size = self._client.mtu_size - 3
        if self._mtu_size < 20:
            self._mtu_size = 20
        logger.info("BLE 연결 성공: %s (MTU write size: %d)", self._address, self._mtu_size)
        await self._client.start_notify(NOTIFY_UUID, self._on_notify)
        self._connected = True

    async def disconnect(self) -> None:
        if self._client and self._connected:
            try:
                await self._client.stop_notify(NOTIFY_UUID)
            except Exception:
                pass
            await self._client.disconnect()
            self._connected = False
            logger.info("BLE 연결 해제: %s", self._address)

    async def ensure_connected(self) -> bool:
        if self._connected and self._client and self._client.is_connected:
            return True
        try:
            await self.connect()
            return True
        except Exception as e:
            logger.error("재연결 실패: %s", e)
            self._connected = False
            return False

    # ── iDotMatrix 이미지 전송 프로토콜 ──

    def _build_image_payloads(self, png_bytes: bytes) -> list[bytearray]:
        """PNG 바이트를 iDotMatrix 전송용 청크 리스트로 변환한다.

        각 청크 구조:
          [길이(2B LE), 0x00, 0x00, option, 전체PNG크기(4B LE)] + [PNG 데이터]
        """
        total_size = len(png_bytes)
        payloads = []

        for idx in range(0, total_size, IMAGE_CHUNK_SIZE):
            chunk = png_bytes[idx:idx + IMAGE_CHUNK_SIZE]
            header = bytearray()
            # 2바이트: 청크 + 헤더메타 길이 (little-endian)
            header += struct.pack("<h", len(chunk) + 9)
            # 고정값
            header += bytes([0x00, 0x00])
            # 첫 청크 0x00, 후속 청크 0x02
            header += bytes([0x00 if idx == 0 else 0x02])
            # 전체 PNG 크기 (4바이트 little-endian)
            header += struct.pack("<i", total_size)

            payloads.append(header + bytearray(chunk))

        return payloads

    def _build_gif_payloads(self, gif_bytes: bytes) -> list[bytearray]:
        """GIF 바이트를 iDotMatrix 전송용 청크 리스트로 변환한다.

        각 청크 구조:
          [길이(2B LE), 0x01, 0x00, option, 전체크기(4B LE), CRC32(4B LE), 0x05, 0x00, 0x0D]
          + [GIF 데이터]
        """
        total_size = len(gif_bytes)
        crc = zlib.crc32(gif_bytes) & 0xFFFFFFFF
        payloads = []

        for idx in range(0, total_size, IMAGE_CHUNK_SIZE):
            chunk = gif_bytes[idx:idx + IMAGE_CHUNK_SIZE]
            header = bytearray()
            header += struct.pack("<h", len(chunk) + 16)
            header += bytes([0x01, 0x00])
            header += bytes([0x00 if idx == 0 else 0x02])
            header += struct.pack("<i", total_size)
            header += struct.pack("<I", crc)
            header += bytes([0x05, 0x00, 0x0D])

            payloads.append(header + bytearray(chunk))

        return payloads

    async def _send_payloads(self, payloads: list[bytearray], wait_ack: bool = True) -> bool:
        """청크 리스트를 BLE MTU 단위로 분할하여 전송한다."""
        for idx, payload in enumerate(payloads):
            self._chunk_ack.clear()

            # BLE MTU 크기로 분할 전송 (write without response)
            pos = 0
            while pos < len(payload):
                end = min(pos + self._mtu_size, len(payload))
                chunk = bytes(payload[pos:end])
                await self._client.write_gatt_char(WRITE_UUID, chunk, response=False)
                pos = end

            logger.debug("청크 %d/%d 전송 완료 (%d 바이트)", idx + 1, len(payloads), len(payload))

            # 멀티 청크: 청크 간 ACK 대기 또는 딜레이
            if len(payloads) > 1 and idx < len(payloads) - 1:
                try:
                    await asyncio.wait_for(self._chunk_ack.wait(), timeout=2.0)
                    logger.debug("청크 %d/%d ACK 수신", idx + 1, len(payloads))
                except asyncio.TimeoutError:
                    logger.debug("청크 %d/%d ACK 타임아웃, 딜레이 후 계속", idx + 1, len(payloads))
                    await asyncio.sleep(0.3)

        return True

    async def set_diy_mode(self, enable: bool = True) -> bool:
        """DIY 모드를 활성화/비활성화한다. 이미지 표시에 필요."""
        return await self._send_command(bytes([5, 0, 4, 1, int(enable)]))

    async def send_image(self, image: Image.Image) -> bool:
        """Pillow Image 객체를 LED 디스플레이에 전송한다.

        자동으로 DIY 모드를 활성화한 뒤 이미지를 전송한다.
        """
        if not await self.ensure_connected():
            return False

        try:
            # DIY 모드 최초 1회만 활성화
            if not self._diy_mode_active:
                await self.set_diy_mode(True)
                await asyncio.sleep(0.3)
                self._diy_mode_active = True

            # 64x64 RGB PNG로 변환
            rgb_image = image.convert("RGB").resize((64, 64), Image.Resampling.NEAREST)
            buf = BytesIO()
            rgb_image.save(buf, format="PNG")
            png_bytes = buf.getvalue()

            payloads = self._build_image_payloads(png_bytes)
            logger.info("이미지 전송: %d 바이트, %d 청크", len(png_bytes), len(payloads))

            self._final_ack.clear()
            result = await self._send_payloads(payloads)

            # 디바이스가 프레임을 처리할 때까지 대기 (큐 밀림 방지)
            try:
                await asyncio.wait_for(self._final_ack.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

            return result
        except Exception as e:
            logger.error("이미지 전송 실패: %s", e)
            self._connected = False
            return False

    async def send_gif(self, gif_path: str | Path) -> bool:
        """GIF 파일을 LED 디스플레이에 전송한다."""
        if not await self.ensure_connected():
            return False

        try:
            gif_path = Path(gif_path)
            # 64x64로 리사이즈
            img = Image.open(gif_path)
            if img.size != (64, 64):
                from PIL import ImageSequence
                frames = []
                for frame in ImageSequence.Iterator(img):
                    frames.append(frame.copy().resize((64, 64), Image.Resampling.NEAREST))
                buf = BytesIO()
                frames[0].save(buf, format="GIF", save_all=True,
                               append_images=frames[1:],
                               duration=img.info.get("duration", 100),
                               loop=img.info.get("loop", 0))
                gif_bytes = buf.getvalue()
            else:
                with open(gif_path, "rb") as f:
                    gif_bytes = f.read()

            payloads = self._build_gif_payloads(gif_bytes)
            logger.info("GIF 전송: %d 바이트, %d 청크", len(gif_bytes), len(payloads))
            return await self._send_payloads(payloads, wait_ack=True)
        except Exception as e:
            logger.error("GIF 전송 실패: %s", e)
            self._connected = False
            return False

    # ── 간단한 명령 전송 ──

    async def _send_command(self, cmd: bytes) -> bool:
        if not await self.ensure_connected():
            return False
        try:
            await self._client.write_gatt_char(WRITE_UUID, cmd, response=True)
            return True
        except Exception as e:
            logger.error("명령 전송 실패: %s", e)
            return False

    async def set_brightness(self, level: int) -> bool:
        """밝기를 설정한다 (0-100)."""
        level = max(0, min(100, level))
        return await self._send_command(bytes([5, 0, 4, 0x80, level]))

    async def set_power(self, on: bool) -> bool:
        """전원을 제어한다."""
        return await self._send_command(bytes([5, 0, 7, 1, int(on)]))

    async def clear(self) -> bool:
        """화면을 지운다."""
        return await self._send_command(bytes([3, 0, 0x0A]))

    async def set_fullscreen_color(self, r: int, g: int, b: int) -> bool:
        """전체 화면을 단색으로 채운다."""
        return await self._send_command(bytes([7, 0, 2, 2, r, g, b]))

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
