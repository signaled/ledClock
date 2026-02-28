"""설정 파일 로더 모듈."""

import json
from pathlib import Path

# 기본 설정 경로
_CONFIG_PATH = Path(__file__).parent / "config.json"

# 기본값 — config.json에 누락된 키가 있을 때 사용
_DEFAULTS = {
    "ble": {
        "device_name_prefix": "IDM-",
        "reconnect_interval_sec": 10,
    },
    "display": {
        "brightness": 50,
        "orientation": 0,
    },
    "clock": {
        "format_24h": True,
        "show_seconds": False,
        "date_format": "MM/DD (ddd)",
    },
    "weather": {
        "api_provider": "openweathermap",
        "api_key": "",
        "location": "",
        "update_interval_min": 30,
    },
    "background": {
        "directory": "assets/backgrounds/",
        "rotation_interval_min": 10,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """base 딕셔너리에 override 값을 병합한다 (깊은 병합)."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> dict:
    """설정 파일을 읽어 딕셔너리로 반환한다.

    파일이 없으면 기본값을 사용한다.
    """
    config_path = path or _CONFIG_PATH
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            user_config = json.load(f)
        return _deep_merge(_DEFAULTS, user_config)
    return _DEFAULTS.copy()
