from flask import Flask, abort, jsonify, request
from flask.logging import create_logger
from requests_cache import CachedSession

from gwr_feed import get_item_listing
from gwr_feed_data import FeedConfig, QueryStatus, GwrQuery, request_headers


app = Flask(__name__)
app.config.update({'JSONIFY_MIMETYPE': 'application/feed+json'})

# app.debug = True

config = FeedConfig(
    session=CachedSession(
        allowable_methods=('GET', 'POST'),
        stale_if_error=True,
        cache_control=True,
        backend='memory'),
    logger=create_logger(app),
    headers=request_headers
)


def get_session_token():
    init_response = config.session.get(config.url + config.basket_uri)
    config.logger.debug(
        f"Getting session token: {config.url}")
    config.session_token = init_response.headers.get('Session-Token')


def generate_response(query):
    if not query.status.ok:
        abort(400, description='Errors found: ' +
              ', '.join(query.status.errors))

    config.logger.debug(query)  # log values

    output = get_item_listing(query)
    return jsonify(output)


@app.route('/', methods=['GET'])
@app.route('/journey', methods=['GET'])
def process_listing():
    request_dict = {
        'from_code': request.args.get('from') or GwrQuery.from_code,
        'to_code': request.args.get('to') or GwrQuery.to_code,
        'time_str': request.args.get('at') or GwrQuery.time_str,
        'date_str': request.args.get('on') or GwrQuery.date_str,
        'weeks_ahead_str': request.args.get('weeks') or GwrQuery.weeks_ahead_str
    }

    if not config.session_token:
        get_session_token()

    query = GwrQuery(status=QueryStatus(), config=config, **request_dict)

    return generate_response(query)


app.run(host='0.0.0.0')
