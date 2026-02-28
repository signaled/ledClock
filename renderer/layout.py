"""화면 레이아웃 모듈 — 각 콘텐츠의 위치를 계산한다."""

from PIL import Image

SCREEN_W = 64
SCREEN_H = 64


class Layout:
    """64x64 화면에 콘텐츠를 배치한다."""

    def compose(self, background: Image.Image, ampm: Image.Image, time: Image.Image,
                date: Image.Image, weather_icon: Image.Image,
                temp: Image.Image,
                ) -> list[tuple[Image.Image, tuple[int, int]]]:
        """각 콘텐츠의 (이미지, (x, y)) 리스트를 반환한다."""
        overlays = []

        # AM/PM: 좌상단
        overlays.append((ampm, (2, 2)))

        # 시간: AM/PM 오른쪽
        clock_x = 2 + ampm.width
        overlays.append((time, (clock_x, 2)))

        # 날짜: 오른쪽 정렬
        date_x = SCREEN_W - date.width - 1
        overlays.append((date, (date_x, 18)))

        # 날씨 아이콘: 오른쪽 하단
        icon_x = SCREEN_W - weather_icon.width + 4
        icon_y = SCREEN_H - weather_icon.height + 8
        overlays.append((weather_icon, (icon_x, icon_y)))

        # 온도: 오른쪽 하단에 붙여서
        temp_x = SCREEN_W - temp.width - 1
        temp_y = SCREEN_H - temp.height - 1
        overlays.append((temp, (temp_x, temp_y)))

        return overlays
