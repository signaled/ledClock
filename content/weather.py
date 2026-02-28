"""날씨 콘텐츠 모듈 — 기상청 단기예보 API / Open-Meteo fallback."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# WMO 날씨 코드 → 내부 아이콘 이름 매핑 (Open-Meteo용)
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
    icon_code: str        # 코드 (문자열)
    updated_at: float     # 갱신 시각 (time.time())


def _dummy_data() -> WeatherData:
    """API 실패 시 더미 데이터."""
    return WeatherData(
        temp=0.0, temp_min=0.0, temp_max=0.0,
        condition="sunny", description="데이터 없음",
        humidity=0, icon_code="0", updated_at=time.time(),
    )


# ---------------------------------------------------------------------------
# 기상청 단기예보 API (KMA)
# ---------------------------------------------------------------------------

def _kma_condition(sky: int, pty: int) -> str:
    """기상청 SKY/PTY 코드 → 내부 아이콘 이름."""
    if pty == 1 or pty == 4:
        return "rain"
    if pty == 2:
        return "rain"      # 비/눈
    if pty == 3:
        return "snow"
    # 강수 없음 → 하늘상태 기준
    if sky == 1:
        return "sunny"
    if sky == 3:
        return "partly_cloudy"
    return "cloudy"         # sky == 4


def _kma_base_time_ncst(now: datetime) -> tuple[str, str]:
    """초단기실황 base_date/base_time 계산. 매시 정각, 10분 이후 호출 가능."""
    if now.minute < 10:
        now = now - timedelta(hours=1)
    return now.strftime("%Y%m%d"), now.strftime("%H00")


def _kma_base_time_fcst(now: datetime) -> tuple[str, str]:
    """단기예보 base_date/base_time 계산. 1일 8회 발표, 10분 이후 호출 가능."""
    base_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    # 현재 시각 기준 가장 최근 발표시각
    cur = now.hour * 60 + now.minute
    selected = None
    selected_date = now
    for h in reversed(base_hours):
        available = h * 60 + 10  # 발표 후 10분
        if cur >= available:
            selected = h
            break
    if selected is None:
        # 자정~02:10 → 전날 23시 발표
        selected = 23
        selected_date = now - timedelta(days=1)
    return selected_date.strftime("%Y%m%d"), f"{selected:02d}00"


class KmaWeatherProvider:
    """기상청 단기예보 API에서 날씨를 가져온다."""

    BASE_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"

    def __init__(self, service_key: str, nx: int = 58, ny: int = 125,
                 cache_min: int = 30, **_kwargs):
        self._service_key = service_key
        self._nx = nx
        self._ny = ny
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
            logger.info("날씨 갱신(기상청): %.1f°C %s 습도%d%%",
                        data.temp, data.condition, data.humidity)
            return data
        except Exception as e:
            logger.error("기상청 API 호출 실패: %s", e)
            if self._cached:
                return self._cached
            return _dummy_data()

    async def _fetch(self) -> WeatherData:
        """초단기실황 + 단기예보를 조합하여 WeatherData를 만든다."""
        import aiohttp

        now = datetime.now()
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession() as session:
            # 1) 초단기실황 — 현재 기온, 습도, 강수형태
            ncst_date, ncst_time = _kma_base_time_ncst(now)
            ncst = await self._call_api(
                session, "getUltraSrtNcst",
                ncst_date, ncst_time, num_of_rows=10, timeout=timeout,
            )

            # 2) 단기예보 — 최저/최고 기온, 하늘상태
            fcst_date, fcst_time = _kma_base_time_fcst(now)
            fcst = await self._call_api(
                session, "getVilageFcst",
                fcst_date, fcst_time, num_of_rows=300, timeout=timeout,
            )

        # 초단기실황 파싱
        temp = 0.0
        humidity = 0
        pty_ncst = 0
        for item in ncst:
            cat = item["category"]
            val = item["obsrValue"]
            if cat == "T1H":
                temp = float(val)
            elif cat == "REH":
                humidity = int(float(val))
            elif cat == "PTY":
                pty_ncst = int(float(val))

        # 단기예보 파싱 — TMN, TMX, SKY, PTY
        temp_min = temp
        temp_max = temp
        sky = 1
        pty_fcst = 0
        today = now.strftime("%Y%m%d")
        tomorrow = (now + timedelta(days=1)).strftime("%Y%m%d")
        # 오늘 TMN/TMX가 없으면 내일 값 사용 (야간 발표 시)
        tmn_found = False
        tmx_found = False
        # 가장 가까운 시간의 SKY/PTY 추출
        closest_sky_time = None
        closest_sky_diff = 9999
        cur_hhmm = now.strftime("%H00")

        for item in fcst:
            cat = item["category"]
            fdate = item["fcstDate"]
            ftime = item["fcstTime"]
            val = item["fcstValue"]

            if cat == "TMN":
                if fdate == today:
                    temp_min = float(val)
                    tmn_found = True
                elif fdate == tomorrow and not tmn_found:
                    temp_min = float(val)
            elif cat == "TMX":
                if fdate == today:
                    temp_max = float(val)
                    tmx_found = True
                elif fdate == tomorrow and not tmx_found:
                    temp_max = float(val)
            elif cat == "SKY" and (fdate == today or fdate == tomorrow):
                diff = abs(int(ftime) - int(cur_hhmm))
                if fdate == tomorrow:
                    diff += 2400  # 내일은 우선순위 낮게
                if diff < closest_sky_diff:
                    closest_sky_diff = diff
                    closest_sky_time = (fdate, ftime)
                    sky = int(val)
            elif cat == "PTY" and closest_sky_time and fdate == closest_sky_time[0] and ftime == closest_sky_time[1]:
                pty_fcst = int(val)

        # 강수형태: 실황 우선, 없으면 예보
        pty = pty_ncst if pty_ncst != 0 else pty_fcst
        condition = _kma_condition(sky, pty)

        sky_desc = {1: "맑음", 3: "구름많음", 4: "흐림"}
        pty_desc = {0: "", 1: "비", 2: "비/눈", 3: "눈", 4: "소나기"}
        desc = pty_desc.get(pty, "") if pty != 0 else sky_desc.get(sky, "맑음")

        return WeatherData(
            temp=temp,
            temp_min=temp_min,
            temp_max=temp_max,
            condition=condition,
            description=desc,
            humidity=humidity,
            icon_code=f"SKY{sky}/PTY{pty}",
            updated_at=time.time(),
        )

    async def _call_api(self, session, operation: str,
                        base_date: str, base_time: str,
                        num_of_rows: int, timeout) -> list[dict]:
        """기상청 API 단일 호출."""
        # serviceKey는 이미 인코딩된 상태일 수 있으므로 URL에 직접 삽입
        url = (
            f"{self.BASE_URL}/{operation}"
            f"?serviceKey={self._service_key}"
            f"&numOfRows={num_of_rows}&pageNo=1&dataType=JSON"
            f"&base_date={base_date}&base_time={base_time}"
            f"&nx={self._nx}&ny={self._ny}"
        )

        async with session.get(url, timeout=timeout) as resp:
            resp.raise_for_status()
            result = await resp.json()

        header = result["response"]["header"]
        if header["resultCode"] != "00":
            raise RuntimeError(f"기상청 API 오류: {header['resultCode']} {header['resultMsg']}")

        return result["response"]["body"]["items"]["item"]


# ---------------------------------------------------------------------------
# Open-Meteo (fallback)
# ---------------------------------------------------------------------------

class OpenMeteoWeatherProvider:
    """Open-Meteo API에서 날씨를 가져온다 (API 키 불필요)."""

    API_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, lat: float = 37.5665, lon: float = 126.9780,
                 cache_min: int = 30, **_kwargs):
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
            logger.info("날씨 갱신(Open-Meteo): %.1f°C %s", data.temp, data.condition)
            return data
        except Exception as e:
            logger.error("Open-Meteo API 호출 실패: %s", e)
            if self._cached:
                return self._cached
            return _dummy_data()

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


# ---------------------------------------------------------------------------
# 팩토리 함수
# ---------------------------------------------------------------------------

def create_weather_provider(config: dict):
    """config에 따라 적절한 날씨 provider를 생성한다."""
    provider = config.get("api_provider", "open-meteo")
    cache_min = config.get("update_interval_min", 30)

    if provider == "kma":
        service_key = config.get("service_key", "")
        if not service_key:
            logger.warning("기상청 API 키 없음, Open-Meteo로 대체")
            return OpenMeteoWeatherProvider(
                lat=config.get("lat", 37.4786),
                lon=config.get("lon", 126.8666),
                cache_min=cache_min,
            )
        return KmaWeatherProvider(
            service_key=service_key,
            nx=config.get("nx", 58),
            ny=config.get("ny", 125),
            cache_min=cache_min,
        )

    return OpenMeteoWeatherProvider(
        lat=config.get("lat", 37.4786),
        lon=config.get("lon", 126.8666),
        cache_min=cache_min,
    )
