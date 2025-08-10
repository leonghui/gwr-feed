from datetime import datetime
from logging import Logger
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from requests_cache.models import AnyResponse
from requests_cache.session import CachedSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.types import SupportedQuery
from config import FeedConfig


class ErrorItem(BaseModel):
    title: str
    detail: str
    user_friendly: dict


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
)
def get_mobile_search_response(
    query: SupportedQuery, query_date: datetime
) -> JourneyResponse | ErrorResponse | None:
    config: FeedConfig = query.config
    logger: Logger = config.logger
    session: CachedSession = config.session
    url: str = config.mobile_search_url
    header: str = f"{query.journey} {query_date.isoformat()}"

    payload = {
        "destination-nlc": str(query.to_id),
        "journey-type": "single",
        "origin-nlc": str(query.from_id),
        "outward-time": query_date.isoformat() + "Z",
        "outward-time-type": "leaving",
        "passenger-groups": [{"adults": 1, "children": 0, "number-of-railcards": 0}],
    }

    logger.debug(msg=f"{header} - querying search endpoint")
    response: AnyResponse = session.post(
        url, headers=config.mobile_headers, json=payload
    )
    logger.debug(msg=f"{header} - response cached: {response.from_cache}")

    response.raise_for_status()  # HTTP errors bubble up for retry

    data = response.json()

    # Determine which response model applies
    if not response.ok and data.get("errors"):
        try:
            return ErrorResponse.model_validate(obj=data)
        except ValidationError as ve:
            logger.error(msg=f"{header} - ErrorResponse validation error: {ve}")
            return None
    else:
        try:
            return JourneyResponse.model_validate(obj=data)
        except ValidationError as ve:
            logger.error(msg=f"{header} - JourneyResponse validation error: {ve}")
            return None
