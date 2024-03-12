import json
from datetime import datetime, timedelta
from flask import abort
from requests.exceptions import JSONDecodeError, RequestException

from croniter import croniter
from json_feed_data import JSONFEED_VERSION_URL, JsonFeedItem, JsonFeedTopLevel
from gwr_feed_data import DatetimeQuery, CronQuery


def get_response_dict(url, query, body):
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


def get_top_level_feed(query, feed_items):

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


def generate_items(query, result_dict):
    item_title_list = [query.config.domain, query.journey]

    if isinstance(query, CronQuery):
        item_title_list.append(query.job_str)

    item_title_text = " - ".join(item_title_list)

    def get_price_entry(date, price):
        return f"{date.isoformat(timespec='minutes')}: {price}"

    iso_timestamp = datetime.now().isoformat("T")

    item_link_url = query.config.base_url

    content_body_list = [
        f"{get_price_entry(date, price)}" for date, price in result_dict.items()
    ]

    content_body = "<br/>".join(content_body_list)

    feed_item = JsonFeedItem(
        id=iso_timestamp,
        url=item_link_url,
        title=item_title_text,
        content_html=content_body + "<br/>" if content_body else "",
        date_published=iso_timestamp,
    )

    return feed_item


def get_request_bodies(query, dates):
    request_dict = {}
    for date in dates:
        request_body = {
            "data": {
                "adults": 1,
                "destinationNlc": str(query.to_id),
                "originNlc": str(query.from_id),
                "outwardDateTime": date.isoformat(),
                "outwardDepartAfter": True,
                "railcards": [],
            }
        }
        request_dict[date] = request_body

    return request_dict


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


def get_item_listing(query):

    dates = get_dates(query)

    request_dict = get_request_bodies(query, dates)

    result_dict = {}

    for date, body in request_dict.items():

        json_dict = get_response_dict(query.config.journey_url, query, body)

        if json_dict:
            journeys = json_dict["data"]["outwardservices"]

            filtered_journeys = None

            if journeys:
                # assume next journey is closest to requested time
                filtered_journeys = [
                    journey
                    for journey in journeys
                    if datetime.fromisoformat(journey["departuredatetime"]) >= date
                ]

            if filtered_journeys:
                first_journey = filtered_journeys[0]

                departure_dt = datetime.fromisoformat(
                    first_journey["departuredatetime"]
                )

                fares = first_journey["cheapestfareselection"]

                if isinstance(fares, dict):
                    fare_types = first_journey["otherfaregroups"]

                    selected_fare = fares["cheapest"]

                    selected_fare_type = [
                        fare_type
                        for fare_type in fare_types
                        if fare_type["faregroupid"]
                        == selected_fare["singlefaregroupid"]
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
            result_dict[date] = "Not found"

    feed_items = generate_items(query, result_dict)

    json_feed = get_top_level_feed(query, [feed_items])

    return json_feed
