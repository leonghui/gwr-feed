from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Annotated, Self, TypeAlias

from croniter import croniter
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    PositiveInt,
    StringConstraints,
    computed_field,
    model_validator,
)
from pydantic_core import PydanticCustomError


@dataclass
class QueryStatus:
    ok: bool = True
    errors: list[str] = field(default_factory=list)

    def refresh(self) -> None:
        self.ok = not self.errors


StationCode: TypeAlias = Annotated[
    str, StringConstraints(to_upper=True, min_length=3, max_length=3)
]


def modify_key(orig_key: str) -> str:
    return orig_key.replace("_arg", "")


class BaseQueryModel(BaseModel):
    from_arg: StationCode = "BHM"
    to: StationCode = "EUS"

    def get_journey(self) -> str:
        return self.from_arg.upper() + ">" + self.to.upper()

    model_config = ConfigDict(
        alias_generator=modify_key, populate_by_name=True, validate_assignment=True
    )


class DatetimeQueryModel(BaseQueryModel):
    at: time = datetime.now().time()
    on: date = datetime.now().date()
    weeks_ahead: PositiveInt = 0

    @computed_field
    @property
    def dt(self) -> datetime:
        combined_dt: datetime = datetime.combine(date=self.on, time=self.at)

        if combined_dt < datetime.now():
            return datetime.combine(
                date=datetime.today() + timedelta(days=1), time=self.at
            )
        else:
            return combined_dt

    @model_validator(mode="after")
    def check_future_dt(self) -> Self:
        if self.dt < datetime.now():
            # https://github.com/pallets-eco/flask-pydantic/pull/96
            raise PydanticCustomError(
                "dt_future",
                "Date and time must be in the future",
            )
        return self


def is_valid_cron_expression(value: str) -> str:
    if not croniter.is_valid(expression=value):
        raise ValueError(f"Invalid cron expression {value}")
    return value


CronExpression: TypeAlias = Annotated[
    str, AfterValidator(func=is_valid_cron_expression)
]


class CronQueryModel(BaseQueryModel):
    job: CronExpression = "0 8 * * 1-5"  #   0800 every weekday
    skip_weeks: PositiveInt = 0


class SearchModel(BaseQueryModel):
    from_id: str
    to_id: str
