from dataclasses import dataclass, field
from datetime import datetime
from logging import Logger

from croniter import croniter
from requests_cache import CachedSession

from gwr_location import get_station_id


CURRENCY_CODE = "£"
GWR_DOMAIN = "gwr.com"
GWR_API_URL = "https://api." + GWR_DOMAIN
GWR_BASE_URL = "https://www." + GWR_DOMAIN
LOCATIONS_SEARCH_URI = "/rail/locations"
FAVICON_URI = "/img/favicons/favicon.ico"
QUERY_LIMIT = 4
X_APP_KEY = "69a273923b31ee667d3593235f91211be1a34232"
APP_VERSION = "4.52.0"
MOBILE_BASE_URL = "https://prod.mobileapi." + GWR_DOMAIN
MOBILE_SEARCH_URI = "/api/v3/train/ticket/search"

mobile_request_headers = {
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
    url: str = GWR_API_URL
    base_url: str = GWR_BASE_URL
    favicon_url: str = GWR_BASE_URL + FAVICON_URI
    domain: str = GWR_DOMAIN
    locations_url: str = GWR_API_URL + LOCATIONS_SEARCH_URI
    currency: str = CURRENCY_CODE
    mobile_search_url: str = MOBILE_BASE_URL + MOBILE_SEARCH_URI
    mobile_headers: dict = field(default_factory=lambda: mobile_request_headers)


@dataclass
class QueryStatus:
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def refresh(self):
        self.ok = not self.errors


@dataclass(kw_only=True)
class _BaseQuery:
    status: QueryStatus
    config: FeedConfig
    from_code: str = "BHM"
    to_code: str = "EUS"
    from_id: str = ""
    to_id: str = ""
    journey: str = ""

    def init_station_ids(self, feed_config):
        self.from_id = get_station_id(self.from_code, feed_config)
        self.to_id = get_station_id(self.to_code, feed_config)

        if not (self.from_id and self.to_id):
            self.status.errors.append("Missing station id(s)")

    def init_journey(self):
        self.journey = self.from_code.upper() + ">" + self.to_code.upper()

    def validate_station_code(self):
        try:
            station_code_rules = [
                self.from_code.isalpha(),
                len(self.from_code) == 3,
                self.to_code.isalpha(),
                len(self.to_code) == 3,
            ]

            if not all(station_code_rules):
                raise TypeError()

        except (TypeError, AttributeError):
            self.status.errors.append("Invalid station code(s)")


@dataclass()
class DatetimeQuery(_BaseQuery):

    time_str: str = datetime.now().strftime("%H%M")
    date_str: str = datetime.now().strftime("%Y%m%d")
    query_dt: datetime = datetime.now()
    weeks_ahead_str: str = "0"
    weeks_ahead: int = 0

    def init_query_dt(self):
        self.query_dt = datetime.strptime(
            self.date_str + " " + self.time_str, "%Y%m%d %H%M"
        )

    def init_weeks_ahead(self):
        if self.weeks_ahead_str:
            self.weeks_ahead = int(self.weeks_ahead_str)

    def validate_departure_time(self):
        if self.time_str:
            time_rules = [self.time_str.isnumeric(), len(self.time_str) == 4]

            if not all(time_rules):
                self.status.errors.append("Invalid departure time")

    def validate_departure_date(self):
        if self.date_str:
            date_rules = [self.date_str.isnumeric(), len(self.date_str) == 8]

            if not all(date_rules):
                self.status.errors.append("Invalid departure date")

    def validate_weeks_ahead(self):
        if self.weeks_ahead_str:
            if not self.weeks_ahead_str.isnumeric():
                self.status.errors.append("Invalid week count")

    def __post_init__(self):
        self.validate_station_code()
        self.validate_departure_time()
        self.validate_departure_date()
        self.validate_weeks_ahead()
        self.status.refresh()

        if self.status.ok:
            self.init_station_ids(self.config)
            self.init_journey()
            self.init_query_dt()
            self.init_weeks_ahead()
            self.status.refresh()


@dataclass()
class CronQuery(_BaseQuery):

    job_str: str = "0 8 * * 1-5"  #   0800 every weekday
    count_str: str = str(QUERY_LIMIT)
    count: int = QUERY_LIMIT
    skip_weeks_str: str = "0"
    skip_weeks: int = 0

    def init_count(self):
        if self.count_str:
            self.count = int(self.count_str)

    def init_skip_weeks(self):
        if self.skip_weeks_str:
            self.skip_weeks = int(self.skip_weeks_str)

    def validate_job(self):
        if self.job_str:
            if not croniter.is_valid(self.job_str):
                self.status.errors.append("Invalid cron expression")

    def validate_count(self):
        if self.count_str:
            count_rules = [
                self.count_str.isnumeric,
                1 <= int(self.count_str) <= QUERY_LIMIT,
            ]

            if not all(count_rules):
                self.status.errors.append("Invalid count")

    def validate_skip_weeks(self):
        if self.skip_weeks_str:
            if not self.skip_weeks_str.isnumeric():
                self.status.errors.append("Invalid skipped week count")

    def __post_init__(self):
        self.validate_station_code()
        self.validate_job()
        self.validate_count()
        self.validate_skip_weeks()
        self.status.refresh()

        if self.status.ok:
            self.init_station_ids(self.config)
            self.init_journey()
            self.init_count()
            self.init_skip_weeks()
            self.status.refresh()
