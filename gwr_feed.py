from datetime import datetime, timedelta
import json
import concurrent.futures

from croniter import croniter
from flask import abort
from requests.exceptions import JSONDecodeError, RequestException

from gwr_feed_data import CronQuery, DatetimeQuery
from json_feed_data import JSONFEED_VERSION_URL, JsonFeedItem, JsonFeedTopLevel


def get_response_dict(url, query: DatetimeQuery, body):
    config = query.config
    logger = config.logger
    session = config.session
    log_header = f"{query.journey} {body['data']['outwardDateTime']}"

    cookies = {"access_token_v2": config.session_token}

    logger.debug(f"{log_header} - querying endpoint: {url}")

    try:
        response = session.post(url, cookies=cookies, json=body)
    except RequestException as rex:
        logger.error(f"{log_header} - {type(rex)}: {rex}")
        return None

    # return HTTP error code
    if not response.ok:
        if response.status_code == 400 and "past" in response.text:
            # ignore errors due to past departure dates
            return None

        if response.status_code == 500 and "20003" in response.text:
            logger.info(f"{log_header} - no fares found")
            return None

        error_body = (
            (
                "Request headers:\n"
                f"{response.request.headers}"
                "\n\nResponse text:\n"
                f"{response.text}"
            )
            if config.debug
            else None
        )

        logger.error(f"{log_header} - HTTP {response.status_code}")
        abort(response.status_code, error_body)
    else:
        logger.debug(f"{log_header} - response cached: {response.from_cache}")
    try:
        return response.json()
    except JSONDecodeError as jdex:
        logger.error(f"{log_header} - HTTP {response.status_code} {type(jdex)}: {jdex}")
        return None


def get_top_level_feed(query: DatetimeQuery, feed_items):

    title_strings = [query.config.domain, query.journey]

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


def generate_items(query: DatetimeQuery, result_dict):
    item_title_list = [query.config.domain, query.journey]

    if isinstance(query, CronQuery):
        item_title_list.append(query.job_str)

    item_title_text = " - ".join(item_title_list)

    def get_price_entry(_dt: datetime, fare_text):
        return f"{_dt.replace(tzinfo=None).isoformat(timespec='minutes')}: {fare_text}"

    iso_timestamp = datetime.now().replace(microsecond=0).isoformat("T")

    item_link_url = query.config.base_url

    content_body_list = [
        f"{get_price_entry(_dt, fare_text)}" for _dt, fare_text in result_dict.items()
    ]
    content_text_body = "\n\n".join(content_body_list)
    content_html_body = "<br/>".join(content_body_list)

    feed_item = JsonFeedItem(
        id=iso_timestamp,
        url=item_link_url,
        title=item_title_text,
        content_text=content_text_body + "\n\n" if content_text_body else "",
        content_html=content_html_body + "<br/>" if content_html_body else "",
        date_published=iso_timestamp,
    )

    return feed_item


def has_departed(message_dict: dict):
    message_text = str(message_dict.get("message-text"))
    if message_text:
        return "already departed" in message_text
    else:
        return False


def mobile_worker(query: DatetimeQuery, _date: datetime, result_dict: dict):
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

    logger.debug(f"{log_header} - querying endpoint: {url}")

    response = session.post(
        url=url, headers=config.mobile_headers, data=json.dumps(data)
    )

    if not response.ok:
        error_dict = response.json().get("errors")
        if (
            response.status_code == 400
            and error_dict
            and error_dict[0].get("title") == "20003"
        ):
            logger.info(f"{log_header} - no fares found")
            result_dict[_date] = "Not found"
            return

        logger.error(f"{log_header} - HTTP {response.status_code}")

        error_body = (
            (
                "Request headers:\n"
                f"{response.request.headers}"
                "\n\nResponse text:\n"
                f"{response.text}"
            )
            if config.debug
            else None
        )

        abort(response.status_code, error_body)

    search_dict = response.json()

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
        result_dict[_date] = "Not found"
        return

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

    result_dict[journey_dt] = fare_text


def get_request_body(query: DatetimeQuery, _date):

    return {
        "data": {
            "adults": 1,
            "destinationNlc": str(query.to_id),
            "originNlc": str(query.from_id),
            "outwardDateTime": _date.isoformat(),
            "outwardDepartAfter": True,
            "railcards": [],
        }
    }


def web_worker(query: DatetimeQuery, _date: datetime, result_dict: dict):
    body = get_request_body(query, _date)

    json_dict = get_response_dict(query.config.journey_url, query, body)

    if json_dict:
        journeys = json_dict["data"]["outwardservices"]

        filtered_journeys = None

        if journeys:
            # assume next journey is closest to requested time
            filtered_journeys = [
                journey
                for journey in journeys
                if datetime.fromisoformat(journey["departuredatetime"]) >= _date
            ]

        if filtered_journeys:
            first_journey = filtered_journeys[0]

            departure_dt = datetime.fromisoformat(first_journey["departuredatetime"])

            fares = first_journey["cheapestfareselection"]

            if isinstance(fares, dict):
                fare_types = first_journey["otherfaregroups"]

                selected_fare = fares["cheapest"]

                selected_fare_type = [
                    fare_type
                    for fare_type in fare_types
                    if fare_type["faregroupid"] == selected_fare["singlefaregroupid"]
                ][0]

                remaining_seats = selected_fare_type["availablespaces"]
                fare_type_name = selected_fare_type["faregroupname"]

                fare_price = "{:.2f}".format(selected_fare["singlefarecost"] / 100)

                fare_text = [
                    query.config.currency,
                    fare_price,
                    f"({fare_type_name})",
                ]

                #   'availablespaces' appears to be defaulted to 9 so we will ignore that
                if query.seats_left and remaining_seats and remaining_seats != 9:
                    fare_text.insert(2, f"({remaining_seats} left)")

                result_dict[departure_dt] = " ".join(fare_text)
    else:
        result_dict[_date] = "Not found"


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

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(dates))

    result_dict = {}

    for _date in dates:
        pool.submit(worker_type(query, _date, result_dict))

    pool.shutdown(wait=True)

    feed_items = generate_items(query, result_dict)

    return feed_items


# Default to using mobile API calls which are faster but do not return remaining seats
def get_item_listing(query: DatetimeQuery, use_mobile_api=True):
    feed_items = get_pooled_results(
        query, mobile_worker if use_mobile_api else web_worker
    )

    json_feed = get_top_level_feed(query, [feed_items])

    return json_feed
