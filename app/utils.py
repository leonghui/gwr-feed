from datetime import datetime, timedelta

from croniter.croniter import croniter

from app.types import BaseQueryModel, CronQueryModel, DatetimeQueryModel
from config import RESULTS_LIMIT, FeedConfig
from mobile.search import Journey, JourneyResponse, Message, SingleFare


def _has_departed(message: Message) -> bool:
    return "already departed" in str(message.message_text)


def _find_closest_journey(
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


def _find_matching_fare(closest_journey: Journey) -> SingleFare | None:
    cheapest_fare: int = closest_journey.cheapest_price

    single_std_fares: list[SingleFare] = closest_journey.single_fares.standard_class

    return next(
        (fare for fare in single_std_fares if fare.price == cheapest_fare),
        None,
    )


def get_dates(query: BaseQueryModel) -> list[datetime]:
    if isinstance(query, DatetimeQueryModel):
        return (
            [query.dt + timedelta(days=(7 * x)) for x in range(query.weeks_ahead + 1)]
            if query.weeks_ahead
            else [query.dt]
        )

    elif isinstance(query, CronQueryModel):
        start_time: datetime = datetime.now() + timedelta(days=(7 * query.skip_weeks))
        cron_iter: croniter[float] = croniter(
            expr_format=query.job, start_time=start_time
        )
        return [cron_iter.get_next(datetime) for _ in range(0, RESULTS_LIMIT)]
    else:
        # unsupported query type
        raise RuntimeError("Unsupported query type")


def _format_fare_text(price_pennies: int, fare_name: str) -> str:
    return f"£{price_pennies / 100:.2f} ({fare_name})"


def extract_fare_text(
    config: FeedConfig, response: JourneyResponse, query_date: datetime
) -> str | None:
    journeys: list[Journey] = response.data.outward

    closest_journey: Journey | None = _find_closest_journey(journeys, query_date)

    if not closest_journey:
        return config.na_text

    matching_fare: SingleFare | None = _find_matching_fare(closest_journey)

    if not matching_fare:
        return config.na_text

    cheapest_fare: int = closest_journey.cheapest_price

    return _format_fare_text(
        price_pennies=cheapest_fare, fare_name=matching_fare.fare_name
    )
