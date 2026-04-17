from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    api_key: str
    api_host: str
    base_url: str
    live_matches_path: str
    home_endpoint: str
    scorecard_path_template: str
    scorecard_endpoint: str
    commentary_path_template: str
    commentary_endpoint: str
    match_info_path_template: str
    match_info_endpoint: str
    timeout_seconds: int = 20


def get_config() -> AppConfig:
    file_values = _load_local_config()

    api_key = _pick_config_value(
        env_keys=["APIHUB_KEY", "RAPIDAPI_KEY"],
        file_values=file_values,
        file_keys=[
            "APIHUB_KEY",
            "RAPIDAPI_KEY",
            "api_key",
            "x-api-key",
            "x_rapidapi_key",
            "x-atd-key",
            "x-apihub-key",
        ],
    ).strip()
    if not api_key:
        api_key = _prompt_required_secret(
            "Enter your API key",
            "Missing API key. Set APIHUB_KEY, add it to .env / rapidapi_config.json, or enter it when prompted.",
        )

    api_host = _pick_config_value(
        env_keys=["APIHUB_HOST", "RAPIDAPI_HOST"],
        file_values=file_values,
        file_keys=[
            "APIHUB_HOST",
            "RAPIDAPI_HOST",
            "api_host",
            "x-api-host",
            "x_rapidapi_host",
            "x-apihub-host",
        ],
        default="Cricbuzz-Official-Cricket-API.allthingsdev.co",
    ).strip()
    home_endpoint = _pick_config_value(
        env_keys=["HOME_ENDPOINT", "APIHUB_ENDPOINT"],
        file_values=file_values,
        file_keys=["HOME_ENDPOINT", "APIHUB_ENDPOINT", "home_endpoint", "api_endpoint", "x-apihub-endpoint"],
        default="95df5edd-bd8b-4881-a12b-1a40e519b693",
    ).strip()
    base_url = _pick_config_value(
        env_keys=["API_BASE_URL", "RAPIDAPI_BASE_URL"],
        file_values=file_values,
        file_keys=["API_BASE_URL", "RAPIDAPI_BASE_URL", "base_url"],
        default="https://Cricbuzz-Official-Cricket-API.proxy-production.allthingsdev.co",
    ).strip()
    live_matches_path = _pick_config_value(
        env_keys=["LIVE_MATCHES_PATH", "RAPIDAPI_LIVE_MATCHES_PATH"],
        file_values=file_values,
        file_keys=["LIVE_MATCHES_PATH", "RAPIDAPI_LIVE_MATCHES_PATH", "live_matches_path"],
        default="/home",
    ).strip()
    scorecard_path_template = _pick_config_value(
        env_keys=["SCORECARD_PATH", "RAPIDAPI_SCORECARD_PATH"],
        file_values=file_values,
        file_keys=["SCORECARD_PATH", "RAPIDAPI_SCORECARD_PATH", "scorecard_path_template", "scorecard_path"],
        default="/match/{match_id}/scorecard",
    ).strip()
    scorecard_endpoint = _pick_config_value(
        env_keys=["SCORECARD_ENDPOINT"],
        file_values=file_values,
        file_keys=["SCORECARD_ENDPOINT", "scorecard_endpoint"],
        default="5f260335-c228-4005-9eec-318200ca48d6",
    ).strip()
    commentary_path_template = _pick_config_value(
        env_keys=["COMMENTARY_PATH"],
        file_values=file_values,
        file_keys=["COMMENTARY_PATH", "commentary_path_template", "commentary_path"],
        default="/match/{match_id}/commentary",
    ).strip()
    commentary_endpoint = _pick_config_value(
        env_keys=["COMMENTARY_ENDPOINT"],
        file_values=file_values,
        file_keys=["COMMENTARY_ENDPOINT", "commentary_endpoint"],
        default="8cb69a0f-bcaa-45b5-a016-229a2e7594f6",
    ).strip()
    match_info_path_template = _pick_config_value(
        env_keys=["MATCH_INFO_PATH"],
        file_values=file_values,
        file_keys=["MATCH_INFO_PATH", "match_info_path_template", "match_info_path"],
        default="/match/{match_id}",
    ).strip()
    match_info_endpoint = _pick_config_value(
        env_keys=["MATCH_INFO_ENDPOINT"],
        file_values=file_values,
        file_keys=["MATCH_INFO_ENDPOINT", "match_info_endpoint"],
        default="ac951751-d311-4d23-8f18-353e75432353",
    ).strip()

    return AppConfig(
        api_key=api_key,
        api_host=api_host,
        base_url=base_url,
        live_matches_path=live_matches_path,
        home_endpoint=home_endpoint,
        scorecard_path_template=scorecard_path_template,
        scorecard_endpoint=scorecard_endpoint,
        commentary_path_template=commentary_path_template,
        commentary_endpoint=commentary_endpoint,
        match_info_path_template=match_info_path_template,
        match_info_endpoint=match_info_endpoint,
    )


def _load_local_config() -> dict[str, str]:
    values: dict[str, str] = {}
    values.update(_read_dotenv(Path(".env")))
    values.update(_read_json_config(Path("rapidapi_config.json")))
    return values


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip().strip("\"'")
    return parsed


def _read_json_config(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    parsed: dict[str, str] = {}
    for key, value in data.items():
        if value not in (None, ""):
            parsed[str(key)] = str(value)
    return parsed


def _pick_config_value(
    *,
    env_keys: list[str],
    file_values: dict[str, str],
    file_keys: list[str],
    default: str = "",
) -> str:
    for key in env_keys:
        value = os.getenv(key, "")
        if value.strip():
            return value

    for key in file_keys:
        value = file_values.get(key, "")
        if value.strip():
            return value

    return default


def _prompt_required_secret(prompt: str, error_message: str) -> str:
    if not sys.stdin.isatty():
        raise RuntimeError(error_message)

    value = getpass(f"{prompt}: ").strip()
    if not value:
        raise RuntimeError(error_message)
    return value
