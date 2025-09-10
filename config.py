from dataclasses import dataclass, field
from logging import Logger

from requests_cache import CachedSession


GWR_DOMAIN = "gwr.com"
GWR_API_URL = "https://api." + GWR_DOMAIN
GWR_BASE_URL = "https://www." + GWR_DOMAIN
LOCATIONS_SEARCH_URI = "/rail/locations"
FAVICON_URI = "/img/favicons/favicon.ico"
X_APP_KEY = "69a273923b31ee667d3593235f91211be1a34232"
APP_VERSION = "4.58.0"
MOBILE_BASE_URL = "https://prod.mobileapi." + GWR_DOMAIN
MOBILE_SEARCH_URI = "/api/v3/train/ticket/search"
FARE_NA_TEXT = "Not found"

mobile_request_headers: dict[str, str] = {
    "Accept-Encoding": "gzip",
    "AppVersion": APP_VERSION,
    "Content-Type": "application/json; charset=UTF-8",
    "User-Agent": "okhttp/4.10.0",
    "X-App-Key": X_APP_KEY,
    "X-App-Platform": "Android",
}


@dataclass()
class FeedConfig:
    session: CachedSession
    logger: Logger
    debug: bool = False
    base_url: str = GWR_BASE_URL
    favicon_url: str = GWR_BASE_URL + FAVICON_URI
    domain: str = GWR_DOMAIN
    locations_url: str = GWR_API_URL + LOCATIONS_SEARCH_URI
    mobile_search_url: str = MOBILE_BASE_URL + MOBILE_SEARCH_URI
    mobile_headers: dict = field(default_factory=lambda: mobile_request_headers)
    na_text: str = FARE_NA_TEXT


config: FeedConfig = FeedConfig(
    session=CachedSession(
        allowable_methods=("GET", "POST"),
        stale_if_error=True,
        cache_control=False,
        expire_after=300,
        backend="memory",
    ),
    logger=Logger("gwr-feed"),
)
