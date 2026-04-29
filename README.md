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
- Previous-year matching cycle kWh
- Usage percent difference
- Latest observed usage rate in kW, inferred from changes in the current-cycle
  kWh total
- Latest observed usage delta in kWh
- Amount due
- Days until due
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

The latest observed usage rate is derived locally from the current-cycle kWh
sensor. It does not call another EPB endpoint: when the cycle total increases,
the integration divides the kWh increase by the hours since the previous
observed increase. The entity stays unavailable until at least one increase has
been observed after Home Assistant starts.

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

## Standalone Probe

You can validate credentials and inspect the redacted API shape outside Home
Assistant:

```bash
MYEPB_USERNAME='you@example.com' MYEPB_PASSWORD='...' python3 scripts/probe_myepb.py
```

For local development, keep credentials in an ignored `.env.local` file:

```bash
cp .env.example .env.local
$EDITOR .env.local
set -a
source .env.local
set +a
python3 scripts/probe_myepb.py
```

The probe prints linked power account numbers redacted to the last four
characters plus the top-level keys returned by the usage endpoint.

## Current Limits

- I could verify endpoint shapes and error responses without account
  credentials, but I could not verify live account payloads end-to-end.
- Hourly/daily/monthly comparison endpoints are implemented in the API client
  but not yet exposed as Home Assistant entities. The inferred latest usage
  sensors use the existing current-cycle endpoint to avoid extra polling.
- EPB can change this private API without notice.
