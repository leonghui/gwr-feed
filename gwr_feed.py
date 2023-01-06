import json
from datetime import datetime, timedelta
from flask import abort
from requests.exceptions import JSONDecodeError, RequestException

from json_feed_data import JSONFEED_VERSION_URL, JsonFeedItem, JsonFeedTopLevel


def get_response_dict(url, query, body):
    config = query.config
    logger = config.logger
    session = config.session
    log_header = f"{query.journey} {body['data']['outwardDateTime']}"

    config.headers['Session-Token'] = config.session_token
    session.headers = config.headers

    logger.debug(
        f"{log_header} - querying endpoint: {url}")

    try:
        response = session.post(url, data=json.dumps(body))
    except RequestException as rex:
        logger.error(f"{log_header} - {type(rex)}: {rex}")
        return None

    # return HTTP error code
    if not response.ok:
        if response.status_code == 500 and '20003' in response.text:
            logger.info(
                f"{log_header} - no fares found")
            return None

        logger.error(
            f"{log_header} - HTTP {response.status_code} - {response.title}")
        abort(response.status_code, response.text)
    else:
        logger.debug(
            f"{log_header} - response cached: {response.from_cache}")
    try:
        return response.json()
    except JSONDecodeError as jdex:
        logger.error(
            f"{log_header} - HTTP {response.status_code} {type(jdex)}: {jdex}")
        return None


def get_top_level_feed(query, feed_items):

    title_strings = [query.config.domain, query.journey]

    base_url = query.config.base_url

    json_feed = JsonFeedTopLevel(
        version=JSONFEED_VERSION_URL,
        items=feed_items,
        title=' - '.join(title_strings),
        home_page_url=base_url,
        favicon=base_url + '/favicon.ico'
    )

    return json_feed


def generate_items(query, result_dict):
    item_title_text = query.config.domain + ' - ' + query.journey

    def get_price_entry(date, price):
        return f"{date.isoformat(timespec='minutes')}: {price}"

    iso_timestamp = datetime.now().isoformat('T')

    item_link_url = query.config.base_url

    content_body_list = [
        f"{get_price_entry(date, price)}" for date, price in result_dict.items()]

    content_body = '\n'.join(content_body_list)

    feed_item = JsonFeedItem(
        id=iso_timestamp,
        url=item_link_url,
        title=item_title_text,
        content_text=content_body,
        date_published=iso_timestamp
    )

    return feed_item


def get_request_bodies(query, dates):
    request_dict = {}
    for date in dates:
        request_body = {
            'data':
                {
                    'adults': 1,
                    'destinationNlc': str(query.to_id),
                    'originNlc': str(query.from_id),
                    'outwardDateTime': date.isoformat(),
                    'outwardDepartAfter': True,
                    'railcards': [],
                }
        }
        request_dict[date] = request_body

    return request_dict


def get_item_listing(query):
    query_url = query.config.url + query.config.journey_uri

    dates = [query.timestamp + timedelta(days=(7 * x))
             for x in range(query.weeks_ahead + 1)]

    request_dict = get_request_bodies(query, dates)

    result_dict = {}

    for date, body in request_dict.items():

        json_dict = get_response_dict(query_url, query, body)

        if json_dict:
            journeys = json_dict['data']['outwardservices']

            filtered_journeys = None

            if journeys:
                # assume next journey is closest to requested time
                filtered_journeys = [
                    journey for journey in journeys
                    if datetime.fromisoformat(journey['departuredatetime']) > date]

            if filtered_journeys:
                first_journey = filtered_journeys[0]

                departure_dt = datetime.fromisoformat(
                    first_journey['departuredatetime'])

                fares = first_journey['cheapestfareselection']

                if isinstance(fares, dict):
                    fare_types = first_journey['otherfaregroups']

                    selected_fare = fares['cheapest']

                    selected_fare_type = [
                        fare_type for fare_type in fare_types
                        if fare_type['faregroupid'] == selected_fare['singlefaregroupid']][0]

                    remaining_seats = selected_fare_type['availablespaces']
                    fare_type_name = selected_fare_type['faregroupname']

                    fare_price = '{:.2f}'.format(
                        selected_fare['singlefarecost'] / 100)

                    fare_text = [query.config.currency,
                                 fare_price, f"({fare_type_name})"]

                    if remaining_seats:
                        fare_text.insert(2, f"({remaining_seats} left)")

                    result_dict[departure_dt] = ' '.join(fare_text)
        else:
            result_dict[date] = 'Not found'

    feed_items = generate_items(query, result_dict)

    json_feed = get_top_level_feed(query, [feed_items])

    return json_feed
