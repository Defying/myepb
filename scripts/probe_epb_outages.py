#!/usr/bin/env python3
"""Probe EPB's public outage-map API."""

from __future__ import annotations

import json
import urllib.request

API_BASE_URL = "https://api.epb.com"


def request(path: str):
    req = urllib.request.Request(
        f"{API_BASE_URL}{path}",
        headers={
            "Accept": "application/json",
            "Origin": "https://epb.com",
            "Referer": "https://epb.com/outage-storm-center/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def print_summary(label: str, path: str, collection_key: str) -> None:
    data = request(path)
    print(f"{label}:")
    print(f"  summary={data.get('summary', {})}")
    print(f"  {collection_key}={len(data.get(collection_key, []))}")


def main() -> int:
    print_summary(
        "Energy incidents",
        "/web/api/v2/outages/energy/incidents",
        "incidents",
    )
    print_summary(
        "Energy restores",
        "/web/api/v2/outages/energy/restores",
        "restores",
    )
    print_summary(
        "Fiber incidents",
        "/web/api/v2/outages/fiber/incidents",
        "incidents",
    )
    print_summary(
        "Fiber restores",
        "/web/api/v2/outages/fiber/restores",
        "restores",
    )
    boundary = request("/web/api/v1/boundaries/service-area")
    print("Service area:")
    print(f"  type={boundary.get('type')}")
    print(f"  geometry={boundary.get('geometry', {}).get('type')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
