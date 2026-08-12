from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when configuration required for a requested action is missing."""


@dataclass(frozen=True)
class AmazonConfig:
    """Full Amazon Creators API credentials, needed only to search Amazon's
    catalog directly (the 'amazon' source)."""

    credential_id: str
    credential_secret: str
    partner_tag: str
    country: str = "US"
    api_version: str = "2.2"


@dataclass(frozen=True)
class AppConfig:
    amazon: Optional[AmazonConfig]  # None unless full API credentials are set
    amazon_country: str  # usable for cart/search links even without API creds
    amazon_partner_tag: Optional[str]  # ditto
    musicbrainz_contact: Optional[str]
    discogs_token: Optional[str]


def _load_amazon_api_config() -> Optional[AmazonConfig]:
    credential_id = os.environ.get("AMAZON_CREDENTIAL_ID", "").strip()
    credential_secret = os.environ.get("AMAZON_CREDENTIAL_SECRET", "").strip()
    partner_tag = os.environ.get("AMAZON_PARTNER_TAG", "").strip()
    if not (credential_id and credential_secret and partner_tag):
        return None
    country = os.environ.get("AMAZON_COUNTRY", "US").strip() or "US"
    api_version = os.environ.get("AMAZON_API_VERSION", "2.2").strip() or "2.2"
    return AmazonConfig(
        credential_id=credential_id,
        credential_secret=credential_secret,
        partner_tag=partner_tag,
        country=country,
        api_version=api_version,
    )


def load_config() -> AppConfig:
    return AppConfig(
        amazon=_load_amazon_api_config(),
        amazon_country=os.environ.get("AMAZON_COUNTRY", "US").strip() or "US",
        amazon_partner_tag=os.environ.get("AMAZON_PARTNER_TAG", "").strip() or None,
        musicbrainz_contact=os.environ.get("APP_CONTACT_EMAIL", "").strip() or None,
        discogs_token=os.environ.get("DISCOGS_TOKEN", "").strip() or None,
    )


def require_amazon(config: AppConfig) -> AmazonConfig:
    """Raise a clear ConfigError if Amazon's catalog-search credentials
    aren't set, instead of letting AttributeError/None bubble up."""
    if config.amazon is None:
        raise ConfigError(
            "Amazon isn't configured (missing AMAZON_CREDENTIAL_ID, "
            "AMAZON_CREDENTIAL_SECRET, and/or AMAZON_PARTNER_TAG in .env). "
            "Either fill those in (see README.md), or drop 'amazon' from "
            "the sources you're searching - MusicBrainz and Discogs don't "
            "need any Amazon credentials."
        )
    return config.amazon
