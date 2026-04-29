"""Constants for the MyEPB integration."""

from datetime import timedelta

DOMAIN = "myepb"

CONF_ACCESS_TOKEN = "access_token"
CONF_ACCESS_TOKEN_EXPIRES_ON = "access_token_expires_on"
CONF_PUBLIC_OUTAGES_ONLY = "public_outages_only"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_REFRESH_TOKEN_EXPIRES_ON = "refresh_token_expires_on"

DEFAULT_API_BASE_URL = "https://api.epb.com"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

ATTR_ACCOUNT_NUMBER = "account_number"
ATTR_REFERENCE_ID = "reference_id"
ATTR_SERVICE_ADDRESS = "service_address"
