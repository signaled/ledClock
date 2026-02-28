"""갱신 주기 관리 모듈 — 시간·날씨·배경 갱신 타이밍을 관리한다."""

import time


class Scheduler:
    """주기적 갱신 타이밍을 관리한다."""

    def __init__(self, weather_interval_min: int = 30, bg_interval_min: int = 10):
        self._weather_interval = weather_interval_min * 60
        self._bg_interval = bg_interval_min * 60
        self._last_weather: float = 0
        self._last_bg: float = 0

    def should_update_weather(self) -> bool:
        """날씨 갱신이 필요한지 확인한다."""
        now = time.time()
        if now - self._last_weather >= self._weather_interval:
            self._last_weather = now
            return True
        return False

    def should_update_background(self) -> bool:
        """배경 전환이 필요한지 확인한다."""
        now = time.time()
        if now - self._last_bg >= self._bg_interval:
            self._last_bg = now
            return True
        return False

    def reset(self):
        """모든 타이머를 리셋한다 (즉시 갱신 트리거)."""
        self._last_weather = 0
        self._last_bg = 0
