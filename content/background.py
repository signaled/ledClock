"""배경 이미지 관리 모듈 — 정적 이미지 + GIF 애니메이션 + 동적 배경 지원."""

import logging
import math
import random
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

    def has_backgrounds(self) -> bool:
        """로드된 배경이 있는지 반환한다."""
        return len(self._backgrounds) > 0

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


# --- 시간대별 그라데이션 색상 팔레트 ---
# 각 시간대: (상단 RGB, 하단 RGB)
_TIME_PALETTES = {
    "dawn":    ((10, 10, 50),   (180, 100, 60)),   # 남색 → 주황
    "sunrise": ((180, 100, 60), (100, 170, 230)),   # 주황 → 하늘색
    "day":     ((80, 150, 220), (200, 220, 255)),    # 하늘색 → 밝은 하늘
    "sunset":  ((180, 80, 40),  (80, 30, 100)),      # 주황빨강 → 보라
    "night":   ((5, 5, 20),     (15, 15, 50)),       # 검정 → 남색
}

# 시간대 경계 (시작 시각, 이름)
_TIME_RANGES = [
    (5,  "dawn"),
    (7,  "sunrise"),
    (9,  "day"),
    (17, "sunset"),
    (19, "night"),
]


def _get_time_slot(hour: int, minute: int) -> tuple[tuple, tuple, float]:
    """현재 시각에 해당하는 그라데이션 색상을 반환한다.

    시간대 경계에서 분 단위로 부드럽게 보간한다.
    반환: (상단색, 하단색, 전환비율은 이미 적용됨)
    """
    total = hour * 60 + minute

    # 현재 시간대와 다음 시간대를 찾는다
    cur_name = "night"
    cur_start = 19 * 60
    next_name = "dawn"
    next_start = 5 * 60 + 24 * 60  # 다음날 새벽

    for i, (h, name) in enumerate(_TIME_RANGES):
        start = h * 60
        if total < start:
            # 이전 시간대에 있음
            next_name = name
            next_start = start
            break
        cur_name = name
        cur_start = start
        # 다음 시간대 결정
        if i + 1 < len(_TIME_RANGES):
            next_name = _TIME_RANGES[i + 1][1]
            next_start = _TIME_RANGES[i + 1][0] * 60
        else:
            next_name = "night"
            next_start = 24 * 60  # 자정(night은 wrap)
    else:
        # for 루프가 break 없이 완료됨 → 마지막 시간대(night) 이후
        next_name = "dawn"
        next_start = (5 + 24) * 60

    cur_top, cur_bot = _TIME_PALETTES[cur_name]
    nxt_top, nxt_bot = _TIME_PALETTES[next_name]

    # 전환 구간: 다음 시간대 시작 30분 전부터 보간
    transition_min = 30
    dist_to_next = next_start - total
    if dist_to_next < 0:
        dist_to_next += 24 * 60

    if dist_to_next <= transition_min and dist_to_next > 0:
        t = 1.0 - dist_to_next / transition_min
        top = tuple(int(a + (b - a) * t) for a, b in zip(cur_top, nxt_top))
        bot = tuple(int(a + (b - a) * t) for a, b in zip(cur_bot, nxt_bot))
        return top, bot, t
    return cur_top, cur_bot, 0.0


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    """두 색상을 t(0~1) 비율로 선형 보간한다."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


class DynamicBackground:
    """시간대별 그라데이션 + 날씨 연동 이펙트 동적 배경."""

    def __init__(self):
        # 별 상태 (밤 하늘)
        self._stars: list[tuple[int, int, int]] = []  # (x, y, 밝기)
        self._stars_initialized = False
        # 빗줄기 상태
        self._rain_drops: list[tuple[int, int]] = []  # (x, y)
        # 눈 입자 상태
        self._snow_flakes: list[tuple[float, float]] = []  # (x, y)
        # 구름 상태: (x, y, width, height)
        self._clouds: list[tuple[int, int, int, int]] = []
        # 햇살 반짝임 상태: (x, y, 밝기)
        self._sunlight_spots: list[tuple[int, int, int]] = []
        self._frame_count = 0

    def _init_stars(self, count: int = 25):
        """별 초기 위치/밝기 생성."""
        self._stars = [
            (random.randint(0, SCREEN_W - 1),
             random.randint(0, SCREEN_H - 1),
             random.randint(80, 255))
            for _ in range(count)
        ]
        self._stars_initialized = True

    def _init_rain(self, count: int = 30):
        """빗줄기 초기 위치 생성."""
        self._rain_drops = [
            (random.randint(0, SCREEN_W - 1), random.randint(0, SCREEN_H - 1))
            for _ in range(count)
        ]

    def _init_snow(self, count: int = 20):
        """눈 입자 초기 위치 생성."""
        self._snow_flakes = [
            (random.uniform(0, SCREEN_W - 1), random.uniform(0, SCREEN_H - 1))
            for _ in range(count)
        ]

    def get_frame(self, hour: int, minute: int, condition: str = "sunny") -> Image.Image:
        """현재 시간과 날씨에 맞는 64x64 배경 프레임을 생성한다."""
        self._frame_count += 1

        # 1) 시간대 기반 그라데이션 생성
        top_color, bot_color, _ = _get_time_slot(hour, minute)
        img = Image.new("RGB", (SCREEN_W, SCREEN_H))
        draw = ImageDraw.Draw(img)

        for y in range(SCREEN_H):
            t = y / (SCREEN_H - 1)
            c = _lerp_color(top_color, bot_color, t)
            draw.line([(0, y), (SCREEN_W - 1, y)], fill=c)

        # 2) 날씨 색조 보정
        if condition in ("rain", "thunder"):
            # 어둡고 파란 톤
            img = self._apply_tint(img, tint=(0, 0, 30), darken=0.5)
        elif condition == "snow":
            # 회색 톤
            img = self._apply_tint(img, tint=(20, 20, 25), darken=0.6)
        elif condition in ("cloudy", "partly_cloudy"):
            # 약간 회색 톤
            img = self._apply_tint(img, tint=(10, 10, 10), darken=0.8)

        # tint 적용 후 draw 재생성 (새 이미지 객체에 그리기 위해)
        draw = ImageDraw.Draw(img)

        # 3) 날씨/시간 이펙트 오버레이
        is_night = hour >= 19 or hour < 5

        if is_night and condition in ("sunny", "partly_cloudy", "cloudy"):
            self._draw_stars(draw)

        # 구름 흘러가기 (낮/아침/저녁/새벽 + sunny/partly_cloudy)
        if not is_night and condition in ("sunny", "partly_cloudy"):
            self._draw_clouds(draw)

        # 햇살 반짝임 (낮 시간대 + sunny)
        if 9 <= hour < 17 and condition == "sunny":
            self._draw_sunlight(draw)

        if condition == "rain":
            self._draw_rain(draw)
        elif condition == "snow":
            self._draw_snow(draw)
        elif condition == "thunder":
            self._draw_rain(draw)
            self._draw_lightning(img, draw)

        return img

    def _apply_tint(self, img: Image.Image, tint: tuple, darken: float) -> Image.Image:
        """이미지에 색조 보정 + 어둡게 처리."""
        img = ImageEnhance.Brightness(img).enhance(darken)
        # 색조 오버레이 추가
        overlay = Image.new("RGB", (SCREEN_W, SCREEN_H), tint)
        return Image.blend(img, overlay, 0.2)

    def _init_clouds(self):
        """구름 초기 위치/크기 생성 (2~3개)."""
        count = random.randint(2, 3)
        self._clouds = [
            (random.randint(0, SCREEN_W - 1),
             random.randint(3, 15),
             random.randint(12, 20),
             random.randint(4, 6))
            for _ in range(count)
        ]

    def _draw_clouds(self, draw: ImageDraw.ImageDraw):
        """구름 흘러가기 효과 — 밝은 흰색 타원 (RGB 모드)."""
        if not self._clouds:
            self._init_clouds()

        new_clouds = []
        for x, y, w, h in self._clouds:
            # 메인 타원 (밝은 흰색)
            draw.ellipse(
                [(x - w // 2, y - h // 2), (x + w // 2, y + h // 2)],
                fill=(210, 215, 230),
            )
            # 겹쳐 그려서 구름 모양 만들기
            draw.ellipse(
                [(x - w // 4, y - h // 2 - 1), (x + w // 3, y + h // 3)],
                fill=(200, 205, 220),
            )
            # 오른쪽으로 1px 이동
            nx = x + 1
            if nx - w // 2 > SCREEN_W:
                nx = -(w // 2)
            new_clouds.append((nx, y, w, h))
        self._clouds = new_clouds

    def _init_sunlight(self, count: int = 6):
        """햇살 반짝임 점 초기 생성."""
        self._sunlight_spots = [
            (random.randint(0, SCREEN_W - 1),
             random.randint(0, SCREEN_H // 3),
             random.randint(150, 255))
            for _ in range(count)
        ]

    def _draw_sunlight(self, draw: ImageDraw.ImageDraw):
        """햇살 반짝임 — 상단 영역에 노란/흰 점이 깜빡임."""
        if not self._sunlight_spots:
            self._init_sunlight()

        new_spots = []
        for x, y, brightness in self._sunlight_spots:
            # 밝기 변동
            delta = random.randint(-60, 60)
            b = max(80, min(255, brightness + delta))
            # 노란빛/흰빛 혼합
            if b > 180:
                color = (b, b, b - 30)  # 노란 기미
                draw.point((x, y), fill=color)
            # 가끔 위치 미세 이동
            if self._frame_count % 8 == 0:
                x = random.randint(0, SCREEN_W - 1)
                y = random.randint(0, SCREEN_H // 3)
            new_spots.append((x, y, b))
        self._sunlight_spots = new_spots

    def _draw_stars(self, draw: ImageDraw.ImageDraw):
        """밤하늘 별 반짝임 효과."""
        if not self._stars_initialized:
            self._init_stars()

        new_stars = []
        for x, y, brightness in self._stars:
            # 밝기 변동 (반짝임)
            delta = random.randint(-40, 40)
            b = max(40, min(255, brightness + delta))
            draw.point((x, y), fill=(b, b, b))
            # 가끔 밝은 별은 주변 픽셀도 약하게 표시
            if b > 200:
                dim = b // 3
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < SCREEN_W and 0 <= ny < SCREEN_H:
                        draw.point((nx, ny), fill=(dim, dim, dim))
            new_stars.append((x, y, b))
        self._stars = new_stars

    def _draw_rain(self, draw: ImageDraw.ImageDraw):
        """빗줄기 애니메이션."""
        if not self._rain_drops:
            self._init_rain()

        new_drops = []
        for x, y in self._rain_drops:
            # 대각선 빗줄기 (3픽셀 길이, 밝은 색상)
            draw.line([(x, y), (x + 1, y + 3)], fill=(180, 200, 255), width=1)
            # 아래로 이동 + 약간 대각선
            ny = y + 4
            nx = x + 1
            if ny >= SCREEN_H:
                ny = random.randint(-3, 0)
                nx = random.randint(0, SCREEN_W - 1)
            new_drops.append((nx % SCREEN_W, ny))
        self._rain_drops = new_drops

    def _draw_snow(self, draw: ImageDraw.ImageDraw):
        """눈 입자 애니메이션."""
        if not self._snow_flakes:
            self._init_snow()

        new_flakes = []
        for x, y in self._snow_flakes:
            ix, iy = int(x), int(y)
            if 0 <= ix < SCREEN_W and 0 <= iy < SCREEN_H:
                draw.point((ix, iy), fill=(220, 225, 235))
            # 느리게 아래로 + 좌우 흔들림
            ny = y + 1.0
            nx = x + random.uniform(-0.8, 0.8)
            if ny >= SCREEN_H:
                ny = random.uniform(-2, 0)
                nx = random.uniform(0, SCREEN_W - 1)
            if nx < 0:
                nx += SCREEN_W
            elif nx >= SCREEN_W:
                nx -= SCREEN_W
            new_flakes.append((nx, ny))
        self._snow_flakes = new_flakes

    def _draw_lightning(self, img: Image.Image, draw: ImageDraw.ImageDraw):
        """번개 플래시 효과 (일정 확률)."""
        if random.random() < 0.1:  # 10% 확률
            flash = Image.blend(
                img,
                Image.new("RGB", (SCREEN_W, SCREEN_H), (255, 255, 240)),
                0.6,
            )
            img.paste(flash)
