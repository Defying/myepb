# MyEPB Home Assistant custom integration

This repository contains an experimental Home Assistant custom integration for
EPB Chattanooga's MyEPB account data.

The integration uses the same web APIs that power `epb.com`. Public outage-map
data works without a MyEPB login. Account-specific usage and billing data still
requires your own MyEPB username and password during setup, and Home Assistant
stores refresh tokens after that.

## What It Exposes

For each linked EPB Energy account, the integration creates sensors for:

- Current billing cycle kWh
- Current billing cycle estimated cost
- Current billing cycle average daily kWh and estimated cost
- Latest billing-cycle day kWh, estimated cost, and average power
- Previous-year matching cycle kWh
- Usage percent difference
- Latest observed usage rate in kW, inferred from changes in the current-cycle
  kWh total
- Latest observed usage delta in kWh
- Last 24 hours kWh, estimated cost, average power, previous-year kWh, and
  usage percent difference
- Rolling 30 days kWh, estimated cost, and average daily kWh
- Rolling 12 months kWh, estimated cost, and average monthly kWh
- Bill-cycle consumption, current bill charges, current bill total, past due,
  amount due, and days until due
- PrePay balance, average daily charge, and estimated days left when the account
  is enrolled in PrePay Power

For the public EPB outage map, the integration creates sensors for:

- Energy and fiber customers affected
- Energy and fiber outage incidents
- Energy and fiber repairs in progress
- Energy and fiber customers in repair
- Energy and fiber customers/incidents restored in the outage-map 24-hour window

The current-cycle kWh sensor uses `device_class: energy` and
`state_class: total_increasing`, so it can be used as a utility-style energy
sensor. EPB appears to reset this value at the billing-cycle boundary.

The comparison sensors use EPB's hourly, daily, and monthly comparison
endpoints. The latest observed usage rate is derived locally from the
current-cycle kWh sensor: when the cycle total increases, the integration
divides the kWh increase by the hours since the previous observed increase.
That inferred entity stays unavailable until at least one increase has been
observed after Home Assistant starts.

## Install

1. Copy `custom_components/myepb` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration**.
4. Search for **MyEPB**.
5. Enter the same MyEPB username and password you use on `epb.com` or in the
   MyEPB app, or leave both fields blank to add public outage-map sensors only.

## API Notes

The public MyEPB portal currently bootstraps this backend:

```text
https://api.epb.com
```

The relevant routes discovered from EPB's shipped JavaScript are:

```text
POST /web/api/v1/login/
GET  /web/api/v1/locations/portal
GET  /web/api/v1/accounts/power
POST /web/api/v1/accounts/power
POST /web/api/v1/usage/power/permanent/cycle
POST /web/api/v1/usage/power/permanent/compare/hourly
POST /web/api/v1/usage/power/permanent/compare/daily
POST /web/api/v1/usage/power/permanent/compare/monthly
GET  /web/api/v1/bills/summary/power/{account_number}
GET  /web/api/v1/bills/summary/power/prepay/{account_number}
GET  /web/api/v2/outages/energy/incidents
GET  /web/api/v2/outages/energy/restores
GET  /web/api/v2/outages/fiber/incidents
GET  /web/api/v2/outages/fiber/restores
GET  /web/api/v1/boundaries/service-area
```

Authenticated requests use:

```text
X-User-Token: <access token>
```

The login response includes access and refresh tokens. The integration stores
tokens rather than storing your password in the config entry.

The outage endpoints are public and do not require `X-User-Token`.

## Privacy Notes

- Home Assistant stores MyEPB access and refresh tokens in the config entry.
  The integration does not store your MyEPB password after setup.
- Diagnostics redact tokens, username, account numbers, addresses, GIS IDs,
  premise IDs, phone/email/name fields, and ZIP/unit/location labels.
- Sensor state attributes intentionally avoid account numbers, service
  addresses, GIS IDs, and zone IDs. Those identifiers are only used internally
  to associate Home Assistant entities with the EPB account.
- The Home Assistant integration ignores config-entry API host overrides and
  sends authenticated requests only to `https://api.epb.com`.

## Standalone Probe

You can validate credentials and inspect the redacted API shape outside Home
Assistant:

```bash
MYEPB_USERNAME='you@example.com' MYEPB_PASSWORD='...' python3 scripts/probe_myepb.py
```

For local development, keep credentials in an ignored `.env.local` file:

```bash
cp .env.example .env.local
chmod 600 .env.local
$EDITOR .env.local
python3 scripts/probe_myepb.py
```

The probe reads `.env.local` itself as plain `KEY=VALUE` text. It does not
`source` the file, so a credentials file cannot execute shell commands. The
probe prints the linked power account count plus top-level keys returned by the
usage endpoint.

For deeper endpoint discovery, run:

```bash
python3 scripts/probe_myepb_deep.py
```

The deep probe prints redacted payload shapes for account, billing,
current-cycle usage, and comparison endpoints. It is intended for development
only; review output before sharing it.

## Current Limits

- Live payload shapes have been verified against one residential account; other
  EPB account classes may expose different fields.
- The integration exposes the comparison endpoint totals, but not every
  individual hourly/daily/monthly data point as separate entities.
- EPB can change this private API without notice.
