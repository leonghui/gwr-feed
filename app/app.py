from datetime import datetime
from multiprocessing.pool import ThreadPool

from app.utils import extract_fare_text, get_dates
from config import FeedConfig
from json_feed.types import JsonFeedItem, JsonFeedTopLevel
from json_feed.utils import generate_items, get_top_level_feed
from mobile.search import ErrorResponse, JourneyResponse, get_mobile_search_response

from .types import SupportedQuery


def _mobile_worker(query: SupportedQuery, query_date: datetime) -> str | None:
    config: FeedConfig = query.config

    response: JourneyResponse | ErrorResponse | None = get_mobile_search_response(
        query, query_date
    )

    if not response or isinstance(response, ErrorResponse):
        return None

    return extract_fare_text(config, response, query_date)


def _fetch_pooled_feed_items(query: SupportedQuery) -> list[JsonFeedItem]:
    dates: list[datetime] = get_dates(query)

    pool_size: int = len(dates)

    with ThreadPool(processes=pool_size) as pool:
        results: list[str | None] = pool.starmap(
            func=_mobile_worker, iterable=[(query, query_date) for query_date in dates]
        )

        result_dict: dict[datetime, str | None] = dict(zip(dates, results))

        return generate_items(query, result_dict)


# Default to using mobile API calls which are faster but do not return remaining seats
def get_item_listing(query: SupportedQuery) -> JsonFeedTopLevel:
    feed_items: list[JsonFeedItem] = _fetch_pooled_feed_items(query)

    return get_top_level_feed(query, feed_items)
