from flask import Flask, jsonify
from flask.wrappers import Response
from flask_pydantic import validate

from app.app import get_item_listing
from app.types import BaseQueryModel, CronQueryModel, DatetimeQueryModel
from config import config
from json_feed.types import JsonFeedTopLevel

app: Flask = Flask(import_name=__name__)
app.config.update({"JSONIFY_MIMETYPE": "application/feed+json"})


def generate_response(query: BaseQueryModel) -> Response:
    config.logger.debug(msg=query)  # log values

    output: JsonFeedTopLevel = get_item_listing(query)
    return jsonify(output)


# handle a single journey
@app.route(rule="/", methods=["GET"])
@app.route(rule="/journey", methods=["GET"])
@validate(response_by_alias=True)
def process_listing(query: DatetimeQueryModel) -> Response:
    return generate_response(query)


# handle repeated journeys using a cron schedule expression
@app.route(rule="/cron", methods=["GET"])
@validate(response_by_alias=True)
def process_cron(query: CronQueryModel) -> Response:
    return generate_response(query)


app.run(host="0.0.0.0", use_reloader=False)
