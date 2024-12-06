from flask import Flask, abort, jsonify
import requests
from requests_cache import CachedSession

from gwr_feed import get_item_listing
from gwr_feed_data import CronQuery, DatetimeQuery, FeedConfig, QueryStatus


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
)


def get_session_token():
    init_response = requests.get(config.basket_url, timeout=10)
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
    params = rq.args
    request_dict = {
        "from_code": params.get("from") or DatetimeQuery.from_code,
        "to_code": params.get("to") or DatetimeQuery.to_code,
        "time_str": params.get("at") or DatetimeQuery.time_str,
        "date_str": params.get("on") or DatetimeQuery.date_str,
        "weeks_ahead_str": params.get("weeks") or DatetimeQuery.weeks_ahead_str,
        "seats_left_str": params.get("seats_left") or DatetimeQuery.seats_left_str,
    }

    # access_token expires after 45 mins, get a new token for each query
    get_session_token()

    query = DatetimeQuery(status=QueryStatus(), config=config, **request_dict)

    return generate_response(query)


@app.route("/cron", methods=["GET"])
def process_cron():
    params = rq.args
    request_dict = {
        "from_code": params.get("from") or CronQuery.from_code,
        "to_code": params.get("to") or CronQuery.to_code,
        "job_str": params.get("job") or CronQuery.job_str,
        "count_str": params.get("count") or CronQuery.count_str,
        "skip_weeks_str": params.get("skip_weeks") or CronQuery.skip_weeks_str,
        "seats_left_str": params.get("seats_left") or CronQuery.seats_left_str,
    }

    # access_token expires after 45 mins, get a new token for each query
    get_session_token()

    query = CronQuery(status=QueryStatus(), config=config, **request_dict)

    return generate_response(query)


app.run(host="0.0.0.0", use_reloader=False)
