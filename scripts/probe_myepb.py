#!/usr/bin/env python3
"""Probe the MyEPB web API with credentials from environment variables."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE_URL = "https://api.epb.com"


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
        raise RuntimeError(f"{method} {path} failed: {err.code} {details}") from err


def redact(value: str) -> str:
    value = str(value)
    return f"...{value[-4:]}" if len(value) > 4 else "..."


def main() -> int:
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

    for location in power_locations:
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
        print(
            f"{redact(account_number)} {location.get('location_label', '')}: "
            f"usage keys={sorted(usage.keys())}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
