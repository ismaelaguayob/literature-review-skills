"""HTTP helpers with local cache, retries, and provider throttling."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback.
    fcntl = None  # type: ignore[assignment]


DEFAULT_CACHE_DIR = Path(".cache/literature-review")
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def load_env(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def provider_config(config: dict[str, Any], provider: str) -> dict[str, Any]:
    apis = config.get("apis", {})
    if provider in apis and isinstance(apis[provider], dict):
        return apis[provider]
    normalized = provider.replace("-", "_")
    if normalized in apis and isinstance(apis[normalized], dict):
        return apis[normalized]
    return {}


def cache_enabled(config: dict[str, Any], provider: str, default: bool = True) -> bool:
    return bool(provider_config(config, provider).get("cache", default))


def retries_for(config: dict[str, Any], provider: str, default: int = 4) -> int:
    try:
        return int(provider_config(config, provider).get("retries", default))
    except (TypeError, ValueError):
        return default


def min_interval_for(config: dict[str, Any], provider: str, default: float = 1.0) -> float:
    try:
        return float(provider_config(config, provider).get("min_interval_seconds", default))
    except (TypeError, ValueError):
        return default


def cache_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@contextmanager
def provider_lock(provider: str):
    lock_dir = DEFAULT_CACHE_DIR / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{provider}.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def throttle(provider: str, min_interval_seconds: float) -> None:
    if min_interval_seconds <= 0:
        return
    with provider_lock(provider):
        state_dir = DEFAULT_CACHE_DIR / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_path = state_dir / f"{provider}.json"
        last_seen = 0.0
        if state_path.exists():
            try:
                last_seen = float(json.loads(state_path.read_text(encoding="utf-8")).get("last_request", 0))
            except (json.JSONDecodeError, ValueError, TypeError):
                last_seen = 0.0
        wait_for = min_interval_seconds - (time.time() - last_seen)
        if wait_for > 0:
            time.sleep(wait_for)
        state_path.write_text(json.dumps({"last_request": time.time()}), encoding="utf-8")


def build_url(url: str, params: dict[str, Any] | None = None) -> str:
    if not params:
        return url
    clean_params = {key: value for key, value in params.items() if value is not None}
    query = urllib.parse.urlencode(clean_params, doseq=True)
    separator = "&" if "?" in url else "?"
    return url + separator + query


def read_cached_json(provider: str, key: str) -> dict[str, Any] | list[Any] | None:
    path = DEFAULT_CACHE_DIR / "api" / provider / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_cached_json(provider: str, key: str, data: dict[str, Any] | list[Any]) -> None:
    path = DEFAULT_CACHE_DIR / "api" / provider / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def request_json(
    url: str,
    *,
    provider: str,
    config: dict[str, Any],
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: int = 45,
    cache: bool | None = None,
) -> dict[str, Any] | list[Any]:
    full_url = build_url(url, params)
    request_payload = {
        "method": method,
        "url": full_url,
        "body": body,
    }
    key = cache_key(request_payload)
    use_cache = cache_enabled(config, provider) if cache is None else cache
    if use_cache:
        cached = read_cached_json(provider, key)
        if cached is not None:
            return cached

    encoded_body = None
    if body is not None:
        encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request_headers = dict(headers or {})
    if encoded_body is not None:
        request_headers.setdefault("Content-Type", "application/json")

    retries = max(1, retries_for(config, provider))
    min_interval = min_interval_for(config, provider)
    for attempt in range(retries):
        throttle(provider, min_interval)
        req = urllib.request.Request(full_url, data=encoded_body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                if use_cache:
                    write_cached_json(provider, key, data)
                return data
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_STATUS and attempt < retries - 1:
                retry_after = exc.headers.get("Retry-After")
                try:
                    sleep_for = float(retry_after) if retry_after else float(2**attempt)
                except ValueError:
                    sleep_for = float(2**attempt)
                time.sleep(max(1.0, sleep_for))
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries - 1:
                time.sleep(float(2**attempt))
                continue
            raise
    raise RuntimeError(f"Failed to request {full_url}")
