#!/usr/bin/env python3
"""Probe the MyEPB web API with credentials from environment variables."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import sys
import urllib.error
import urllib.request

API_BASE_URL = "https://api.epb.com"
LOCAL_ENV_FILE = Path(".env.local")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LONG_NUMBER_RE = re.compile(r"\b\d{5,}\b")


def request(method: str, path: str, *, token: str | None = None, body=None):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-User-Token"] = token

    req = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return True
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        details = err.read().decode()
        raise RuntimeError(
            f"{method} {path} failed: {err.code} {redact_error(details)}"
        ) from err


def load_local_env() -> None:
    """Load simple KEY=VALUE pairs without executing shell code."""

    if not LOCAL_ENV_FILE.exists():
        return

    for line in LOCAL_ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not ENV_KEY_RE.fullmatch(key) or key in os.environ:
            continue
        try:
            parsed = shlex.split(value, comments=False, posix=True)
        except ValueError:
            parsed = [value.strip()]
        os.environ[key] = parsed[0] if len(parsed) == 1 else value.strip()


def redact_error(details: str) -> str:
    details = EMAIL_RE.sub("redacted", details)
    details = LONG_NUMBER_RE.sub("redacted", details)
    return re.sub(
        r'"reference_id"\s*:\s*"[^"]+"',
        '"reference_id":"redacted"',
        details,
    )


def main() -> int:
    load_local_env()
    username = os.environ.get("MYEPB_USERNAME")
    password = os.environ.get("MYEPB_PASSWORD")
    if not username or not password:
        print("Set MYEPB_USERNAME and MYEPB_PASSWORD.", file=sys.stderr)
        return 2

    login = request(
        "POST",
        "/web/api/v1/login/",
        body={"grant_type": "PASSWORD", "username": username, "password": password},
    )
    token = login["tokens"]["access"]["token"]

    locations = request("GET", "/web/api/v1/locations/portal", token=token)
    power_locations = [location for location in locations if location.get("power")]
    print(f"Power locations: {len(power_locations)}")

    for index, location in enumerate(power_locations, start=1):
        power = location["power"]
        premise = location["premise"]
        account_number = str(power["account_number"])
        body = {
            "account_number": account_number,
            "gis_id": str(premise["gis_id"]),
            "zone_id": str(premise["zone_id"]),
        }
        usage = request(
            "POST",
            "/web/api/v1/usage/power/permanent/cycle",
            token=token,
            body=body,
        )
        print(f"Power account {index}: usage keys={sorted(usage.keys())}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
