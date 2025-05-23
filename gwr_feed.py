from multiprocessing.pool import ThreadPool
from datetime import datetime, timedelta
import json

from croniter import croniter
from flask import abort

from gwr_feed_data import CronQuery, DatetimeQuery
from json_feed_data import JSONFEED_VERSION_URL, JsonFeedItem, JsonFeedTopLevel


def get_top_level_feed(query: DatetimeQuery, feed_items):

    title_strings = [query.config.domain, query.journey]

    if isinstance(query, CronQuery):
        title_strings.append(query.job_str)

    base_url = query.config.base_url
    favicon_url = query.config.favicon_url

    json_feed = JsonFeedTopLevel(
        version=JSONFEED_VERSION_URL,
        items=feed_items,
        title=" - ".join(title_strings),
        home_page_url=base_url,
        favicon=favicon_url,
    )

    return json_feed


def generate_items(query: DatetimeQuery, result_dict: dict[datetime, str]):
    title_list = [query.config.domain, query.journey]

    feed_items = []

    for _dt, fare_text in result_dict.items():
        fare_timestamp = _dt.replace(tzinfo=None).isoformat(timespec="minutes")
        item_title_text = title_list + [fare_timestamp]
        published_timestamp = datetime.now().replace(microsecond=0).isoformat("T")

        item_link_url = query.config.base_url

        feed_item = JsonFeedItem(
            id=published_timestamp,
            url=item_link_url,
            title=" - ".join(item_title_text),
            content_text=fare_text,
            content_html=fare_text,
            date_published=published_timestamp,
        )

        feed_items.append(feed_item)

    return feed_items


def has_departed(message_dict: dict):
    message_text = str(message_dict.get("message-text"))
    if message_text:
        return "already departed" in message_text
    else:
        return False


def get_mobile_search_response(query: DatetimeQuery, _date: datetime):
    config = query.config
    logger = config.logger
    session = config.session
    url = config.mobile_search_url

    log_header = f"{query.journey} {_date}"

    data = {
        "destination-nlc": str(query.to_id),
        "journey-type": "single",
        "origin-nlc": str(query.from_id),
        "outward-time": _date.isoformat() + "Z",
        "outward-time-type": "leaving",
        "passenger-groups": [{"adults": 1, "children": 0, "number-of-railcards": 0}],
    }

    logger.debug(f"{log_header} - querying search endpoint")

    response = session.post(
        url=url, headers=config.mobile_headers, data=json.dumps(data)
    )

    logger.debug(f"{log_header} - response is cached: {response.from_cache}")

    return response


def mobile_worker(query: DatetimeQuery, _date: datetime):
    config = query.config
    logger = config.logger

    log_header = f"{query.journey} {_date}"

    search_response = get_mobile_search_response(query=query, _date=_date)

    for i in range(config.retry_count):
        if not search_response.ok:
            logger.warning(f"{log_header} - retrying search endpoint")
            search_response = get_mobile_search_response(query=query, _date=_date)

    if not search_response.ok:
        if search_response.text:
            error_dict = search_response.json().get("errors")
            if (
                search_response.status_code == 400
                and error_dict
                and error_dict[0].get("title") == "20003"
            ):
                logger.info(f"{log_header} - no fares found")
                return config.na_text

        return config.error_text

    search_dict = search_response.json()

    journeys = search_dict.get("data").get("outward")

    valid_journeys = [
        journey
        for journey in journeys
        # assume both query and results are using the same tz
        if datetime.fromisoformat(journey.get("departure-time")).replace(tzinfo=None)
        >= _date
        and not has_departed(journey.get("messages"))
    ]

    # skip if no results
    if not valid_journeys:
        return config.na_text

    closest_journey = min(
        valid_journeys, key=lambda x: datetime.fromisoformat(x["departure-time"])
    )

    cheapest_fare = closest_journey.get("cheapest-price")

    journey_dt = datetime.fromisoformat(closest_journey["departure-time"])

    single_std_fares = closest_journey.get("single-fares").get("standard-class")

    matching_fare = next(
        (fare for fare in single_std_fares if fare.get("price") == cheapest_fare),
        None,
    )

    fare_text = (
        f"£{'{0:.2f}'.format(cheapest_fare / 100)} ({matching_fare.get("fare-name")})"
    )

    return fare_text


def get_dates(query):
    if isinstance(query, DatetimeQuery):
        return [
            query.query_dt + timedelta(days=(7 * x))
            for x in range(query.weeks_ahead + 1)
        ]
    elif isinstance(query, CronQuery):
        base = datetime.now() + timedelta(days=(7 * query.skip_weeks))
        iter = croniter(query.job_str, base)
        return [iter.get_next(datetime) for _ in range(0, query.count)]


def get_pooled_results(query: DatetimeQuery, worker_type):
    dates = get_dates(query)

    with ThreadPool() as pool:
        args = [(query, _date) for _date in dates]
        results = pool.starmap(mobile_worker, args)

        result_dict = dict(zip(dates, results))

        feed_items = generate_items(query, result_dict)

        return feed_items


# Default to using mobile API calls which are faster but do not return remaining seats
def get_item_listing(query: DatetimeQuery):
    feed_items = get_pooled_results(query, mobile_worker)

    json_feed = get_top_level_feed(query, feed_items)

    return json_feed
