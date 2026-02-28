"""배경 이미지 관리 모듈 — 정적 이미지 + GIF 애니메이션 지원."""

import logging
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

SCREEN_W = 64
SCREEN_H = 64


class BackgroundManager:
    """배경 이미지/애니메이션을 관리한다."""

    def __init__(self, bg_dir: str = "assets/backgrounds/", brightness: float = 0.5):
        self._bg_dir = Path(bg_dir)
        self._brightness = brightness
        # 각 배경: (frames_list, is_animated)
        self._backgrounds: list[tuple[list[Image.Image], bool]] = []
        self._current_idx = 0
        self._frame_idx = 0

    def load_all(self) -> int:
        """배경 디렉토리에서 이미지/GIF를 모두 로드한다."""
        self._backgrounds.clear()
        if not self._bg_dir.exists():
            logger.warning("배경 디렉토리 없음: %s", self._bg_dir)
            return 0

        for path in sorted(self._bg_dir.glob("*")):
            ext = path.suffix.lower()
            try:
                if ext == ".gif":
                    frames = self._load_gif(path)
                    if frames:
                        self._backgrounds.append((frames, True))
                        logger.info("GIF 배경 로드: %s (%d프레임)", path.name, len(frames))
                elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
                    bg = self._prepare_static(Image.open(path))
                    self._backgrounds.append(([bg], False))
                    logger.info("배경 로드: %s", path.name)
            except Exception as e:
                logger.warning("배경 로드 실패: %s (%s)", path.name, e)

        return len(self._backgrounds)

    def _detect_bg_color(self, img: Image.Image) -> tuple[int, int, int]:
        """이미지의 배경색을 감지한다 (모서리 픽셀 기반)."""
        rgb = img.convert("RGB")
        w, h = rgb.size
        corners = [
            rgb.getpixel((0, 0)),
            rgb.getpixel((w - 1, 0)),
            rgb.getpixel((0, h - 1)),
            rgb.getpixel((w - 1, h - 1)),
        ]
        return Counter(corners).most_common(1)[0][0]

    def _load_gif(self, path: Path) -> list[Image.Image]:
        """GIF의 모든 프레임을 64x64 캔버스에 중앙 배치하여 로드."""
        gif = Image.open(path)
        bg_color = self._detect_bg_color(gif.copy())

        frames = []
        try:
            while True:
                frame = gif.copy().convert("RGB")
                fw, fh = frame.size

                if fw >= SCREEN_W and fh >= SCREEN_H:
                    # 큰 이미지: 리사이즈
                    canvas = self._prepare_static(frame)
                else:
                    # 작은 픽셀아트: 배경색 캔버스에 원본 크기로 중앙 배치
                    canvas = Image.new("RGB", (SCREEN_W, SCREEN_H), bg_color)
                    x = (SCREEN_W - fw) // 2
                    y = (SCREEN_H - fh) // 2
                    canvas.paste(frame, (x, y))

                frames.append(canvas)
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass
        return frames

    def load_image(self, path: str) -> Image.Image:
        """단일 이미지를 배경으로 준비한다."""
        return self._prepare_static(Image.open(path))

    def get_current(self) -> Image.Image:
        """현재 배경의 첫 프레임을 반환한다. 없으면 기본 그라데이션."""
        if not self._backgrounds:
            return self.default_gradient()
        frames, _ = self._backgrounds[self._current_idx]
        return frames[0]

    def get_frame(self) -> Image.Image:
        """현재 배경의 다음 애니메이션 프레임을 반환한다."""
        if not self._backgrounds:
            return self.default_gradient()
        frames, animated = self._backgrounds[self._current_idx]
        if not animated:
            return frames[0]
        frame = frames[self._frame_idx % len(frames)]
        self._frame_idx += 1
        return frame

    def next(self) -> Image.Image:
        """다음 배경으로 전환한다."""
        if self._backgrounds:
            self._current_idx = (self._current_idx + 1) % len(self._backgrounds)
            self._frame_idx = 0
        return self.get_current()

    def _prepare_static(self, img: Image.Image) -> Image.Image:
        """정적 이미지를 64x64 RGB로 변환하고 밝기를 조절한다."""
        img = img.convert("RGB").resize((SCREEN_W, SCREEN_H), Image.Resampling.LANCZOS)
        if self._brightness < 1.0:
            img = ImageEnhance.Brightness(img).enhance(self._brightness)
        img = ImageOps.posterize(img, 4)
        return img

    @staticmethod
    def default_gradient() -> Image.Image:
        """기본 보라색 그라데이션 배경."""
        img = Image.new("RGB", (SCREEN_W, SCREEN_H))
        draw = ImageDraw.Draw(img)
        for y in range(SCREEN_H):
            r = int(10 + y * 0.4)
            g = int(5 + y * 0.2)
            b = int(40 + y * 0.6)
            draw.line([(0, y), (63, y)], fill=(r, g, b))
        return img
