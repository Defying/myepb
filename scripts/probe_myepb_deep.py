#!/usr/bin/env python3
"""Deep redacted probe for MyEPB account API payload shapes."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
import json
import os
import re
import sys
from typing import Any
import urllib.error
import urllib.request

API_BASE_URL = "https://api.epb.com"

SENSITIVE_KEYS = {
    "access",
    "access_token",
    "account_number",
    "account_holder_display_name",
    "address",
    "billing_address",
    "customer",
    "display_name",
    "email",
    "email_address",
    "expires_on",
    "first_name",
    "full_service_address",
    "gis_id",
    "initials",
    "last_name",
    "label",
    "location_label",
    "name",
    "phone",
    "phone_number",
    "premise_id",
    "refresh",
    "refresh_token",
    "street",
    "token",
    "username",
    "zone_id",
}


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: Any | None = None,
) -> Any:
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
            f"{method} {redact_path(path)} failed: {err.code} {redact_error(details)}"
        ) from err


def redact(value: Any, *, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return _redacted_scalar(value)
    if isinstance(value, dict):
        return {
            item_key: redact(item_value, key=item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value[:3]]
    return value


def shape(value: Any, *, depth: int = 0, max_depth: int = 4) -> Any:
    if depth >= max_depth:
        return type(value).__name__
    if isinstance(value, dict):
        return {
            key: shape(item, depth=depth + 1, max_depth=max_depth)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        if not value:
            return {"type": "list", "len": 0}
        return {
            "type": "list",
            "len": len(value),
            "sample": shape(value[0], depth=depth + 1, max_depth=max_depth),
        }
    return type(value).__name__


def summarize_endpoint(label: str, payload: Any) -> None:
    print(f"\n## {label}")
    print(json.dumps(shape(payload), indent=2, sort_keys=True))
    sample = redact(payload)
    print("sample:")
    print(json.dumps(sample, indent=2, sort_keys=True)[:6000])


def _redacted_scalar(value: Any) -> str:
    if isinstance(value, dict):
        return "{redacted}"
    if isinstance(value, list):
        return "[redacted]"
    return "redacted"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in SENSITIVE_KEYS:
        return True
    return any(
        marker in lowered
        for marker in (
            "account",
            "address",
            "email",
            "gis",
            "name",
            "phone",
            "premise",
            "token",
            "zip",
        )
    )


def redact_path(path: str) -> str:
    return re.sub(r"\d{5,}", "redacted", path)


def redact_error(details: str) -> str:
    redacted = re.sub(r"\d{5,}", "redacted", details)
    redacted = re.sub(
        r'"reference_id"\s*:\s*"[^"]+"',
        '"reference_id":"redacted"',
        redacted,
    )
    return redacted[:500]


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for candidate in (text, text[:10]):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def compare_field_candidates(
    cycle_usage: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    today = date.today()
    start = parse_date(cycle_usage.get("current_cycle_start_date")) or today
    end = parse_date(cycle_usage.get("current_cycle_end_date")) or today
    day = min(max(start, today - timedelta(days=7)), today)
    return {
        "hourly": [
            {"year": day.year, "month": day.month, "day": day.day},
            {"start_date": day.isoformat(), "end_date": day.isoformat()},
            {"date": day.isoformat()},
            {"usage_date": day.isoformat()},
        ],
        "daily": [
            {"year": start.year, "month": start.month},
            {"start_date": start.isoformat(), "end_date": end.isoformat()},
            {"from_date": start.isoformat(), "to_date": end.isoformat()},
        ],
        "monthly": [
            {"year": today.year},
            {
                "start_date": date(today.year, 1, 1).isoformat(),
                "end_date": today.isoformat(),
            },
        ],
    }


def try_compare_endpoints(
    token: str,
    body_base: dict[str, str],
    cycle_usage: dict[str, Any],
) -> None:
    print("\n## comparison endpoint trials")
    for period, candidates in compare_field_candidates(cycle_usage).items():
        for fields in candidates:
            try:
                payload = request(
                    "POST",
                    f"/web/api/v1/usage/power/permanent/compare/{period}",
                    token=token,
                    body={**body_base, **fields},
                )
            except RuntimeError as err:
                print(f"{period} fields={fields}: error={err}")
                continue
            print(f"{period} fields={fields}: ok")
            summarize_endpoint(f"compare/{period}", payload)
            break


def account_body_from_location(location: dict[str, Any]) -> dict[str, str]:
    power = location["power"]
    premise = location["premise"]
    return {
        "account_number": str(power["account_number"]),
        "gis_id": str(premise["gis_id"]),
        "zone_id": str(premise["zone_id"]),
    }


def required_env(names: Iterable[str]) -> dict[str, str]:
    values = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        print(f"Set {', '.join(missing)}.", file=sys.stderr)
        raise SystemExit(2)
    return values


def main() -> int:
    env = required_env(("MYEPB_USERNAME", "MYEPB_PASSWORD"))
    login = request(
        "POST",
        "/web/api/v1/login/",
        body={
            "grant_type": "PASSWORD",
            "username": env["MYEPB_USERNAME"],
            "password": env["MYEPB_PASSWORD"],
        },
    )
    token = login["tokens"]["access"]["token"]
    summarize_endpoint("login", login)

    locations = request("GET", "/web/api/v1/locations/portal", token=token)
    summarize_endpoint("locations/portal", locations)
    power_locations = [location for location in locations if location.get("power")]

    account_links = request("GET", "/web/api/v1/account-links/", token=token)
    summarize_endpoint("account-links", account_links)

    power_accounts = request("GET", "/web/api/v1/accounts/power", token=token)
    summarize_endpoint("accounts/power GET", power_accounts)

    if not power_locations:
        print("No power locations found.")
        return 0

    body = account_body_from_location(power_locations[0])
    selected_accounts = request(
        "POST",
        "/web/api/v1/accounts/power",
        token=token,
        body=[body["account_number"]],
    )
    summarize_endpoint("accounts/power POST", selected_accounts)

    cycle_usage = request(
        "POST",
        "/web/api/v1/usage/power/permanent/cycle",
        token=token,
        body=body,
    )
    summarize_endpoint("usage cycle", cycle_usage)

    try:
        bill_summary = request(
            "GET",
            f"/web/api/v1/bills/summary/power/{body['account_number']}",
            token=token,
        )
        summarize_endpoint("bill summary", bill_summary)
    except RuntimeError as err:
        print(f"\n## bill summary\n{err}")

    try:
        prepay_summary = request(
            "GET",
            f"/web/api/v1/bills/summary/power/prepay/{body['account_number']}",
            token=token,
        )
        summarize_endpoint("prepay summary", prepay_summary)
    except RuntimeError as err:
        print(f"\n## prepay summary\n{err}")

    try_compare_endpoints(token, body, cycle_usage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
