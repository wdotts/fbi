from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when required Amazon API configuration is missing."""


@dataclass(frozen=True)
class AmazonConfig:
    credential_id: str
    credential_secret: str
    partner_tag: str
    country: str = "US"
    api_version: str = "2.2"


def load_amazon_config() -> AmazonConfig:
    """Load Amazon Creators API credentials from the environment.

    Raises ConfigError with a user-facing message if anything required
    is missing, instead of letting a bare KeyError bubble up.
    """
    credential_id = os.environ.get("AMAZON_CREDENTIAL_ID", "").strip()
    credential_secret = os.environ.get("AMAZON_CREDENTIAL_SECRET", "").strip()
    partner_tag = os.environ.get("AMAZON_PARTNER_TAG", "").strip()
    country = os.environ.get("AMAZON_COUNTRY", "US").strip() or "US"
    api_version = os.environ.get("AMAZON_API_VERSION", "2.2").strip() or "2.2"

    missing = [
        name
        for name, value in (
            ("AMAZON_CREDENTIAL_ID", credential_id),
            ("AMAZON_CREDENTIAL_SECRET", credential_secret),
            ("AMAZON_PARTNER_TAG", partner_tag),
        )
        if not value
    ]
    if missing:
        raise ConfigError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in your Amazon Creators "
            "API credentials (see README.md for how to obtain them)."
        )

    return AmazonConfig(
        credential_id=credential_id,
        credential_secret=credential_secret,
        partner_tag=partner_tag,
        country=country,
        api_version=api_version,
    )
