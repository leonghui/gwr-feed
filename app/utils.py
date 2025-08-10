from datetime import datetime, timedelta

from croniter.croniter import croniter

from app.types import CronQuery, DatetimeQuery, SupportedQuery
from mobile.search import Journey, Message, SingleFare


def _has_departed(message: Message | dict) -> bool:
    if isinstance(message, Message):
        return "already departed" in message.message_text
    else:
        return False


def find_closest_journey(
    journeys: list[Journey], query_date: datetime
) -> Journey | None:
    valid_journeys: list[Journey] = [
        journey
        for journey in journeys
        # assume both query and results are using the same tz
        if journey.departure_time.replace(tzinfo=None) >= query_date
        and not _has_departed(message=journey.messages)
    ]

    return (
        min(valid_journeys, key=lambda x: x.departure_time) if valid_journeys else None
    )


def find_matching_fare(closest_journey: Journey) -> SingleFare | None:
    cheapest_fare: int = closest_journey.cheapest_price

    single_std_fares: list[SingleFare] = closest_journey.single_fares.standard_class

    return next(
        (fare for fare in single_std_fares if fare.price == cheapest_fare),
        None,
    )


def get_dates(query: SupportedQuery) -> list[datetime]:
    if isinstance(query, DatetimeQuery):
        return [
            query.query_dt + timedelta(days=(7 * x))
            for x in range(query.weeks_ahead + 1)
        ]
    elif isinstance(query, CronQuery):
        base: datetime = datetime.now() + timedelta(days=(7 * query.skip_weeks))
        iter: croniter[float] = croniter(expr_format=query.job_str, start_time=base)
        return [iter.get_next(datetime) for _ in range(0, query.count)]
