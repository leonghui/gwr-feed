import requests
from flask import Flask, abort, jsonify, request as rq
from requests_cache import CachedSession

from gwr_feed import get_item_listing
from gwr_feed_data import FeedConfig, QueryStatus, GwrQuery, request_headers


app = Flask(__name__)
app.config.update({"JSONIFY_MIMETYPE": "application/feed+json"})

# app.debug = True

config = FeedConfig(
    debug=app.debug,
    session=CachedSession(
        allowable_methods=("GET", "POST"),
        stale_if_error=True,
        cache_control=False,
        expire_after=300,
        backend="memory",
    ),
    logger=app.logger,
    headers=request_headers,
)


def get_session_token():
    basket_url = config.url + config.basket_uri
    init_response = requests.get(basket_url, timeout=10)
    new_session_token = init_response.headers.get("Session-Token")
    if new_session_token:
        config.logger.debug(f"Received new session token: {new_session_token}")
        config.session_token = new_session_token


def generate_response(query):
    if not query.status.ok:
        abort(400, description="Errors found: " + ", ".join(query.status.errors))

    config.logger.debug(query)  # log values

    output = get_item_listing(query)
    return jsonify(output)


@app.route("/", methods=["GET"])
@app.route("/journey", methods=["GET"])
def process_listing():
    request_dict = {
        "from_code": rq.args.get("from") or GwrQuery.from_code,
        "to_code": rq.args.get("to") or GwrQuery.to_code,
        "time_str": rq.args.get("at") or GwrQuery.time_str,
        "date_str": rq.args.get("on") or GwrQuery.date_str,
        "weeks_ahead_str": rq.args.get("weeks") or GwrQuery.weeks_ahead_str,
        "seats_left_str": rq.args.get("seats_left") or GwrQuery.seats_left_str,
    }

    # access_token expires after 45 mins, get a new token for each query
    get_session_token()

    query = GwrQuery(status=QueryStatus(), config=config, **request_dict)

    return generate_response(query)


app.run(host="0.0.0.0")
