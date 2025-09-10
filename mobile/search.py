from datetime import datetime
from logging import Logger
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from requests import HTTPError
from requests_cache.models import AnyResponse
from requests_cache.session import CachedSession
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.types import BaseQueryModel
from config import config
from web.location import get_station_id


class ErrorItem(BaseModel):
    title: str
    detail: str


class ErrorResponse(BaseModel):
    errors: list[ErrorItem]


class SingleFare(BaseModel):
    id: str
    price: int
    fare_class: str = Field(default=..., alias="fare-class")
    fare_name: str = Field(default=..., alias="fare-name")


class SingleFares(BaseModel):
    standard_class: list[SingleFare] = Field(default=..., alias="standard-class")


class Message(BaseModel):
    message_text: Optional[str] = Field(default=None, alias="message-text")


class Journey(BaseModel):
    id: str
    departure_time: datetime = Field(default=..., alias="departure-time")
    arrival_time: datetime = Field(default=..., alias="arrival-time")
    cheapest_price: int = Field(default=..., alias="cheapest-price")
    messages: Message
    changes: int
    unavailable: bool
    single_fares: SingleFares = Field(default=..., alias="single-fares")


class OutwardData(BaseModel):
    outward: list[Journey]


class JourneyResponse(BaseModel):
    data: OutwardData


@retry(
    stop=stop_after_attempt(max_attempt_number=3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_not_exception_type(exception_types=HTTPError),
)
def get_mobile_search_response(
    query: BaseQueryModel, query_date: datetime
) -> JourneyResponse | ErrorResponse | None:
    logger: Logger = config.logger
    session: CachedSession = config.session
    url: str = config.mobile_search_url
    header: str = f"{query.get_journey()} {query_date.isoformat()}"

    payload = {
        "destination-nlc": get_station_id(station_code=query.to),
        "journey-type": "single",
        "origin-nlc": get_station_id(station_code=query.from_arg),
        "outward-time": query_date.isoformat() + "Z",
        "outward-time-type": "leaving",
        "passenger-groups": [{"adults": 1, "children": 0, "number-of-railcards": 0}],
    }

    logger.debug(msg=f"{header} - querying search endpoint")
    response: AnyResponse = session.post(
        url, headers=config.mobile_headers, json=payload
    )
    logger.debug(msg=f"{header} - response cached: {response.from_cache}")
    # response.raise_for_status()  # HTTP errors bubble up for retry
    data = response.json()

    # Determine which response model applies
    if not response.ok or data.get("errors"):
        try:
            error_response: ErrorResponse = ErrorResponse.model_validate(obj=data)
            error_details: list[str] = [error.detail for error in error_response.errors]
            logger.error(msg=f"{header} - server error: {error_details}")

            raise HTTPError(error_details)

        except ValidationError as ve:
            logger.error(msg=f"{header} - ErrorResponse validation error: {ve}")
            return None
    else:
        try:
            return JourneyResponse.model_validate(obj=data)
        except ValidationError as ve:
            logger.error(msg=f"{header} - JourneyResponse validation error: {ve}")
            return None
