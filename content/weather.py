"""날씨 콘텐츠 모듈 — Open-Meteo API 연동 (API 키 불필요)."""

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# WMO 날씨 코드 → 내부 아이콘 이름 매핑
_WMO_ICON_MAP = {
    0: "sunny",           # Clear sky
    1: "sunny",           # Mainly clear
    2: "partly_cloudy",   # Partly cloudy
    3: "cloudy",          # Overcast
    45: "cloudy",         # Fog
    48: "cloudy",         # Depositing rime fog
    51: "rain",           # Drizzle light
    53: "rain",           # Drizzle moderate
    55: "rain",           # Drizzle dense
    56: "rain",           # Freezing drizzle light
    57: "rain",           # Freezing drizzle dense
    61: "rain",           # Rain slight
    63: "rain",           # Rain moderate
    65: "rain",           # Rain heavy
    66: "rain",           # Freezing rain light
    67: "rain",           # Freezing rain heavy
    71: "snow",           # Snow slight
    73: "snow",           # Snow moderate
    75: "snow",           # Snow heavy
    77: "snow",           # Snow grains
    80: "rain",           # Rain showers slight
    81: "rain",           # Rain showers moderate
    82: "rain",           # Rain showers violent
    85: "snow",           # Snow showers slight
    86: "snow",           # Snow showers heavy
    95: "thunder",        # Thunderstorm
    96: "thunder",        # Thunderstorm with slight hail
    99: "thunder",        # Thunderstorm with heavy hail
}


@dataclass
class WeatherData:
    """날씨 데이터."""
    temp: float           # 현재 기온 (°C)
    temp_min: float       # 최저 기온
    temp_max: float       # 최고 기온
    condition: str        # 내부 아이콘 이름 (sunny, cloudy, rain, ...)
    description: str      # 설명
    humidity: int         # 습도 (%)
    icon_code: str        # WMO 코드 (문자열)
    updated_at: float     # 갱신 시각 (time.time())


class WeatherProvider:
    """Open-Meteo API에서 날씨를 가져온다 (API 키 불필요)."""

    API_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, lat: float = 37.5665, lon: float = 126.9780,
                 location: str = "", cache_min: int = 30, **_kwargs):
        self._lat = lat
        self._lon = lon
        self._cache_min = cache_min
        self._cached: WeatherData | None = None
        self._last_fetch: float = 0

    async def get_weather(self) -> WeatherData:
        """날씨 데이터를 반환한다 (캐시 적용)."""
        now = time.time()
        if self._cached and (now - self._last_fetch) < self._cache_min * 60:
            return self._cached

        try:
            data = await self._fetch()
            self._cached = data
            self._last_fetch = now
            logger.info("날씨 갱신: %.1f°C %s", data.temp, data.condition)
            return data
        except Exception as e:
            logger.error("날씨 API 호출 실패: %s", e)
            if self._cached:
                return self._cached
            return self._dummy_data()

    async def _fetch(self) -> WeatherData:
        """Open-Meteo API를 호출한다."""
        import aiohttp

        params = {
            "latitude": self._lat,
            "longitude": self._lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code",
            "daily": "temperature_2m_min,temperature_2m_max",
            "timezone": "auto",
            "forecast_days": 1,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.API_URL, params=params,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                result = await resp.json()

        current = result["current"]
        daily = result["daily"]
        wmo_code = current["weather_code"]

        return WeatherData(
            temp=current["temperature_2m"],
            temp_min=daily["temperature_2m_min"][0],
            temp_max=daily["temperature_2m_max"][0],
            condition=_WMO_ICON_MAP.get(wmo_code, "sunny"),
            description=f"WMO {wmo_code}",
            humidity=current["relative_humidity_2m"],
            icon_code=str(wmo_code),
            updated_at=time.time(),
        )

    @staticmethod
    def _dummy_data() -> WeatherData:
        """API 실패 시 더미 데이터."""
        return WeatherData(
            temp=3.0,
            temp_min=-1.0,
            temp_max=7.0,
            condition="sunny",
            description="맑음",
            humidity=45,
            icon_code="0",
            updated_at=time.time(),
        )
