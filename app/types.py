from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeAlias

from croniter import croniter

from config import FeedConfig
from web.location import get_station_id

QUERY_LIMIT = 4


@dataclass
class QueryStatus:
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def refresh(self) -> None:
        self.ok = not self.errors


@dataclass(kw_only=True)
class _BaseQuery:
    status: QueryStatus
    config: FeedConfig
    from_code: str = "BHM"
    to_code: str = "EUS"
    from_id: str | None = ""
    to_id: str | None = ""
    journey: str = ""

    def init_station_ids(self, feed_config: FeedConfig) -> None:
        self.from_id = get_station_id(station_code=self.from_code, config=feed_config)
        self.to_id = get_station_id(station_code=self.to_code, config=feed_config)

        if not (self.from_id and self.to_id):
            self.status.errors.append("Missing station id(s)")

        if self.from_id == self.to_id:
            self.status.errors.append("Station id(s) must be different")

    def init_journey(self) -> None:
        self.journey = self.from_code.upper() + ">" + self.to_code.upper()

    def validate_station_code(self) -> None:
        try:
            station_code_rules: list[bool] = [
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
    time_str: str = datetime.now().strftime(format="%H%M")
    date_str: str = datetime.now().strftime(format="%Y%m%d")
    query_dt: datetime = datetime.now()
    weeks_ahead_str: str = "0"
    weeks_ahead: int = 0

    def init_query_dt(self) -> None:
        self.query_dt = datetime.strptime(
            self.date_str + " " + self.time_str, "%Y%m%d %H%M"
        )

    def init_weeks_ahead(self) -> None:
        if self.weeks_ahead_str:
            self.weeks_ahead = int(self.weeks_ahead_str)

    def validate_departure_time(self) -> None:
        if self.time_str:
            time_rules: list[bool] = [
                self.time_str.isnumeric(),
                len(self.time_str) == 4,
            ]

            if not all(time_rules):
                self.status.errors.append("Invalid departure time")

    def validate_departure_date(self) -> None:
        if self.date_str:
            date_rules: list[bool] = [
                self.date_str.isnumeric(),
                len(self.date_str) == 8,
            ]

            if not all(date_rules):
                self.status.errors.append("Invalid departure date")

    def validate_weeks_ahead(self) -> None:
        if self.weeks_ahead_str:
            if not self.weeks_ahead_str.isnumeric():
                self.status.errors.append("Invalid week count")

    def __post_init__(self) -> None:
        self.validate_station_code()
        self.validate_departure_time()
        self.validate_departure_date()
        self.validate_weeks_ahead()
        self.status.refresh()

        if self.status.ok:
            self.init_station_ids(feed_config=self.config)
            self.init_journey()
            self.init_query_dt()
            self.init_weeks_ahead()
            self.status.refresh()


@dataclass()
class CronQuery(_BaseQuery):
    job_str: str = "0 8 * * 1-5"  #   0800 every weekday
    count_str: str = str(QUERY_LIMIT)
    skip_weeks_str: str = "0"
    count: int = 0
    skip_weeks: int = 0

    def init_count(self) -> None:
        if self.count_str:
            self.count = int(self.count_str)

    def init_skip_weeks(self) -> None:
        if self.skip_weeks_str:
            self.skip_weeks = int(self.skip_weeks_str)

    def validate_job(self) -> None:
        if self.job_str:
            if not croniter.is_valid(expression=self.job_str):
                self.status.errors.append("Invalid cron expression")

    def validate_count(self) -> None:
        if self.count_str:
            count_rules = [
                self.count_str.isnumeric,
                1 <= int(self.count_str) <= QUERY_LIMIT,
            ]

            if not all(count_rules):
                self.status.errors.append("Invalid count")

    def validate_skip_weeks(self) -> None:
        if self.skip_weeks_str:
            if not self.skip_weeks_str.isnumeric():
                self.status.errors.append("Invalid skipped week count")

    def __post_init__(self) -> None:
        self.validate_station_code()
        self.validate_job()
        self.validate_count()
        self.validate_skip_weeks()
        self.status.refresh()

        if self.status.ok:
            self.init_station_ids(feed_config=self.config)
            self.init_journey()
            self.init_count()
            self.init_skip_weeks()
            self.status.refresh()


SupportedQuery: TypeAlias = CronQuery | DatetimeQuery
