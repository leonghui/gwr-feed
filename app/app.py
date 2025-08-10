from datetime import datetime
from multiprocessing.pool import ThreadPool

from app.utils import find_closest_journey, find_matching_fare, get_dates
from config import FeedConfig
from json_feed.types import JsonFeedItem, JsonFeedTopLevel
from json_feed.utils import generate_items, get_top_level_feed
from mobile.search import (
    ErrorResponse,
    Journey,
    JourneyResponse,
    SingleFare,
    get_mobile_search_response,
)

from .types import SupportedQuery


def _mobile_worker(query: SupportedQuery, query_date: datetime) -> str | None:
    config: FeedConfig = query.config

    search_response: JourneyResponse | ErrorResponse | None = (
        get_mobile_search_response(query, query_date)
    )

    if not search_response or isinstance(search_response, ErrorResponse):
        return None

    assert isinstance(search_response, JourneyResponse)

    journeys: list[Journey] = search_response.data.outward

    closest_journey: Journey | None = find_closest_journey(journeys, query_date)

    if not closest_journey:
        return config.na_text

    matching_fare: SingleFare | None = find_matching_fare(closest_journey)

    if not matching_fare:
        return config.na_text

    cheapest_fare: int = closest_journey.cheapest_price

    fare_text: str = (
        f"£{'{0:.2f}'.format(cheapest_fare / 100)} ({matching_fare.fare_name})"
    )

    return fare_text


def _fetch_pooled_feed_items(query: SupportedQuery) -> list[JsonFeedItem]:
    dates: list[datetime] = get_dates(query)

    with ThreadPool() as pool:
        args: list[tuple[SupportedQuery, datetime]] = [
            (query, query_date) for query_date in dates
        ]
        results: list[str | None] = pool.starmap(func=_mobile_worker, iterable=args)

        result_dict: dict[datetime, str | None] = dict(zip(dates, results))

        feed_items: list[JsonFeedItem] = generate_items(query, result_dict)

        return feed_items


# Default to using mobile API calls which are faster but do not return remaining seats
def get_item_listing(query: SupportedQuery) -> JsonFeedTopLevel:
    feed_items: list[JsonFeedItem] = _fetch_pooled_feed_items(query)

    json_feed: JsonFeedTopLevel = get_top_level_feed(query, feed_items)

    return json_feed
