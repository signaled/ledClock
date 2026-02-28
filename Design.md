# 설계 문서

## 프로젝트: BLE LED 픽셀 디스플레이 (라즈베리파이)

---

## 1. 전체 아키텍처

```
┌─────────────────────────────────────────────────┐
│                 라즈베리파이                       │
│                                                   │
│  ┌───────────┐  ┌───────────┐  ┌──────────────┐ │
│  │ 날씨 API  │  │ 시간 모듈  │  │ 이미지/GIF   │ │
│  │(Open-Meteo)│  │           │  │ 로더         │ │
│  └─────┬─────┘  └─────┬─────┘  └──────┬───────┘ │
│        │              │               │          │
│        └──────┬───────┴───────┬───────┘          │
│               ▼               ▼                  │
│        ┌─────────────────────────┐               │
│        │    렌더링 엔진           │               │
│        │  (Pillow 64x64 캔버스)   │               │
│        │  - 레이어 합성           │               │
│        │  - 텍스트 렌더링         │               │
│        └───────────┬─────────────┘               │
│                    ▼                             │
│        ┌─────────────────────────┐               │
│        │    BLE 전송 모듈         │               │
│        │  (bleak + DIY 모드)     │               │
│        └───────────┬─────────────┘               │
│                    │ BLE                         │
└────────────────────┼─────────────────────────────┘
                     ▼
          ┌─────────────────────┐
          │  64x64 LED 매트릭스  │
          │  (IDM-44A6B1)       │
          └─────────────────────┘
```

---

## 2. 모듈 구조

```
ledPixelDisplay/
├── main.py                  # 엔트리포인트, 메인 루프 (1초 갱신, 콜론 깜빡임)
├── config.py                # 설정 로드 (config.json)
├── config.json              # 사용자 설정 파일
├── scheduler.py             # 갱신 주기 관리 (날씨 30분, 배경 1분)
│
├── ble/
│   ├── __init__.py
│   ├── connection.py        # BLE 디바이스 스캔·연결·재연결
│   └── sender.py            # DIY 모드 이미지 전송 (ACK 코드 0,1,2 지원)
│
├── renderer/
│   ├── __init__.py
│   ├── canvas.py            # 64x64 Pillow 캔버스 관리
│   ├── layers.py            # 레이어 합성 (NEAREST 리샘플링)
│   ├── layout.py            # 화면 레이아웃 배치
│   └── text.py              # 텍스트 렌더링 (1비트, 3방향 그림자)
│
├── content/
│   ├── __init__.py
│   ├── clock.py             # 시간/날짜 콘텐츠 (혼합 폰트 렌더링)
│   ├── weather.py           # Open-Meteo API 연동 (API 키 불필요)
│   ├── weather_icons.py     # Material Symbols 38x38 날씨 아이콘
│   └── background.py        # 배경 이미지/GIF 관리
│
├── assets/
│   ├── fonts/               # Galmuri 7/9/11 + MaterialSymbols.ttf
│   └── backgrounds/         # 배경 이미지/GIF 파일
│
└── resource/                # 원본 픽셀아트 GIF 리소스
```

---

## 3. 핵심 설계

### 3.1 메인 루프

```python
async def main():
    # 1. config.json 로드
    # 2. 모듈 초기화 (clock, weather, background, layout, scheduler)
    # 3. BLE 디바이스 스캔 및 연결
    # 4. 무한 루프 (1초 간격):
    #    a. 콜론 깜빡임 (초 % 2)
    #    b. 날씨 갱신 체크 (30분 간격)
    #    c. 배경 전환 체크 (1분 간격)
    #    d. 텍스트/아이콘/온도 렌더링
    #    e. 레이어 합성 → 64x64 이미지
    #    f. BLE 전송
```

### 3.2 렌더링 파이프라인

1. **배경 레이어**: 그라데이션 또는 이미지/GIF 프레임 (64x64)
2. **텍스트 레이어**: 1비트 렌더링 (안티앨리어싱 없음) + 3방향 그림자
3. **합성**: `Image.alpha_composite()`로 배경 위에 오버레이
4. **전송**: DIY 모드로 PNG 압축 후 BLE 전송 (4096바이트 청크)

### 3.3 화면 레이아웃 (64x64)

```
┌────────────────────────────────┐
│ AM 12:30              (좌상단) │  ← AM/PM(Galmuri9) + 시간(Galmuri11 12px)
│          02/15 Sun    (우정렬) │  ← 날짜(혼합폰트, 요일색상)
│                                │
│                    ☀           │  ← 날씨 아이콘 (Material Symbols 38x38)
│                   (우하단)     │     오른쪽 +4px, 아래 +10px
│                                │
│              4° 2°/11° (우하단)│  ← 현재온도(주황) + 최저/최고(회색)
└────────────────────────────────┘
```

### 3.4 폰트 설계

| 용도 | 폰트 | 크기 | 스타일 |
|------|------|------|--------|
| AM/PM | Galmuri9 | 9px | regular |
| 시간 | Galmuri11 | 12px | bold |
| 날짜 (한글) | Galmuri9 | 9px | regular, 2px 위로 |
| 날짜 (영문/숫자) | Galmuri7 | 7px | regular |
| 온도 | Galmuri7 | 7px | tiny |

- 날짜: 혼합 폰트 렌더링 (문자별 폰트 선택), 커닝 -1px
- 요일 색상: 평일=흰색, 토=파랑(80,130,255), 일=빨강(255,80,80)
- 모든 텍스트: 3방향 1px 검은 그림자 `(1,0), (0,1), (1,1)` — `alpha_composite`

### 3.5 날씨 아이콘

- **렌더링**: Material Symbols Outlined 폰트 38x38
- **6종**: sunny, partly_cloudy, cloudy, rain, snow, thunder
- **색상**: sunny/thunder=노란, rain=파란, partly_cloudy/cloudy/snow=어두운 회색
- **그림자**: 3방향 1px (텍스트와 동일)
- **WMO 코드 매핑**: Open-Meteo의 WMO weather code → 내부 아이콘 이름

### 3.6 날씨 API

- **Open-Meteo** (무료, API 키 불필요)
- 호출 주기: 30분
- 데이터: 현재 기온, 최저/최고, 습도, WMO 날씨 코드
- 캐싱: 메모리 캐시, API 실패 시 이전 캐시 사용
- 위치: 위도/경도 설정 (기본값: 서울 37.5665, 126.9780)

### 3.7 BLE 전송 전략

- **bleak** 라이브러리로 비동기 BLE 통신
- **DIY 모드**: 첫 전송 시 `[5, 0, 4, 1, 1]` 명령으로 활성화
- **Write UUID**: `0000fa02`, **Notify UUID**: `0000fa03`
- **ACK 코드**: 0, 1, 2 = 청크 ACK, 3 = 최종 완료
- **PNG 최적화**: posterize(4bit) + 밝기 조절로 1청크(4096바이트) 이내 유지
- **리샘플링**: NEAREST (LANCZOS에서 변경 — 픽셀 아티팩트 방지)
- 전송 간격: 1초 (정적 화면)

### 3.8 설정 파일 구조 (config.json)

```json
{
  "ble": {
    "device_name_prefix": "IDM-",
    "reconnect_interval_sec": 10
  },
  "display": {
    "brightness": 50,
    "orientation": 0
  },
  "clock": {
    "format_24h": true,
    "show_seconds": false,
    "date_format": "MM/DD (ddd)"
  },
  "weather": {
    "api_provider": "open-meteo",
    "lat": 37.5665,
    "lon": 126.9780,
    "update_interval_min": 30
  },
  "background": {
    "directory": "assets/backgrounds/",
    "rotation_interval_min": 1
  }
}
```

---

## 4. 실행 방법

### 4.1 의존성 설치

```bash
pip install bleak Pillow aiohttp
```

### 4.2 실행

```bash
python main.py
```

- BLE 디바이스(IDM-*)가 근처에 있어야 자동으로 스캔·연결됨
- 연결 후 1초 간격으로 화면을 갱신하며 `Ctrl+C`로 종료

### 4.3 테스트/미리보기 스크립트

| 스크립트 | 설명 |
|----------|------|
| `preview_icons.py` | 날씨 아이콘 및 전체 레이아웃을 PC에서 PNG로 미리보기 (10배 확대) |
| `test_icons.py` | 날씨 아이콘을 LED 디바이스에 순차 전송하여 테스트 |

### 4.4 설정 파라미터 (config.json)

#### `ble` — BLE 연결

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `device_name_prefix` | string | `"IDM-"` | 스캔 시 디바이스 이름 필터 접두사 |
| `reconnect_interval_sec` | int | `10` | 연결 끊김 시 재연결 시도 간격 (초) |

#### `display` — 디스플레이

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `brightness` | int | `50` | LED 밝기 (0–100) |
| `orientation` | int | `0` | 화면 회전 (0, 90, 180, 270) |
| `fps` | int | `1` | 화면 갱신 FPS (정적 화면은 1 권장) |

#### `clock` — 시계

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `format_24h` | bool | `true` | 24시간제 사용 여부 (false 시 AM/PM 표시) |
| `show_seconds` | bool | `false` | 초 표시 여부 |
| `date_format` | string | `"MM/DD (ddd)"` | 날짜 포맷 |

#### `weather` — 날씨

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `api_provider` | string | `"open-meteo"` | 날씨 API 제공자 |
| `lat` | float | `37.5665` | 위도 (기본값: 서울) |
| `lon` | float | `126.9780` | 경도 (기본값: 서울) |
| `update_interval_min` | int | `30` | 날씨 데이터 갱신 주기 (분) |

#### `background` — 배경

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `directory` | string | `"assets/backgrounds/"` | 배경 이미지 디렉토리 경로 |
| `rotation_interval_min` | int | `1` | 배경 이미지 전환 주기 (분) |

---

## 5. 데이터 흐름

```
[Open-Meteo] ──(HTTP)──→ [weather.py] ──→ ┐
[시스템 시계] ──────────→ [clock.py]  ──→  ├→ [layout.py] → [layers.py] → 64x64 Image
[이미지/GIF] ──────────→ [background.py]→ ┘        │
                                                    ▼
                                           [sender.py] → BLE DIY → LED
```

---

## 6. TODO 목록

### Phase 1: 기반 구축
- [x] **T-01**: 프로젝트 디렉토리 구조 생성 및 의존성 설치 (`bleak`, `Pillow`, `aiohttp`)
- [x] **T-02**: `config.json` 설정 파일 및 `config.py` 로더 구현
- [x] **T-03**: `ble/connection.py` — BLE 디바이스 스캔·연결·재연결 모듈 구현
- [x] **T-04**: `ble/sender.py` — DIY 모드 이미지 전송 (ACK 핸들링 포함)
- [x] **T-05**: BLE 연결 및 테스트 이미지 전송 검증

### Phase 2: 렌더링 엔진
- [x] **T-06**: `renderer/canvas.py` — 64x64 Pillow 캔버스 기본 구현
- [x] **T-07**: `renderer/text.py` — 1비트 렌더링, 혼합 폰트, 3방향 그림자
- [x] **T-08**: `renderer/layers.py` — 레이어 합성 (NEAREST 리샘플링)

### Phase 3: 콘텐츠 모듈
- [x] **T-09**: `content/clock.py` — AM/PM, 시간(콜론 깜빡임), 날짜(영문 요일, 요일 색상)
- [x] **T-10**: `content/weather.py` — Open-Meteo API 연동 (WMO 코드 매핑, 30분 캐싱)
- [x] **T-11**: 날씨 아이콘 — Material Symbols 38x38 (6종 + 그림자)
- [x] **T-12**: `content/background.py` — 배경 이미지/GIF 로더 (배경색 감지, 중앙 배치)

### Phase 4: 통합 및 스케줄링
- [x] **T-13**: `scheduler.py` — 날씨(30분)·배경(1분) 갱신 주기 관리
- [x] **T-14**: `main.py` — 메인 루프 (1초 갱신, 콜론 깜빡임, 캐싱 최적화)
- [x] **T-15**: `renderer/layout.py` — 화면 레이아웃 (AM/PM, 시간, 날짜, 아이콘, 온도)

### Phase 5: 시스템 운영
- [ ] **T-16**: `log.py` — 로깅 설정
- [ ] **T-17**: systemd 서비스 파일 작성 (라즈베리파이 자동 시작)
- [ ] **T-18**: 에러 핸들링 보강 (BLE 끊김 자동 재연결, API 실패 복구)

### Phase 6: 개선
- [ ] **T-19**: GIF 애니메이션 배경 (보류 — FPS 제어 및 최적화 필요)
- [ ] **T-20**: 시간대별 배경 자동 전환 로직
- [ ] **T-21**: 밝기 자동 조절 (시간대 기반)
- [ ] **T-22**: BLE 스캔 재시도 및 연결 안정성 개선
