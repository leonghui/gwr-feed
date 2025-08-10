from pydantic import BaseModel, ValidationError
from requests_cache.models import AnyResponse
from tenacity import retry, stop_after_attempt, wait_exponential

from config import FeedConfig


class Station(BaseModel):
    name: str
    code: str
    nlc: str
    isfgw: bool
    isgroup: bool
    isalias: bool
    tod: bool


class StationResponse(BaseModel):
    environment: str
    data: list[Station]


@retry(
    stop=stop_after_attempt(max_attempt_number=3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
)
def get_station_id(station_code: str, config: FeedConfig) -> str | None:
    resp: AnyResponse = config.session.get(config.locations_url, expire_after=-1)
    resp.raise_for_status()

    try:
        payload: StationResponse = StationResponse.model_validate(obj=resp.json())
    except ValidationError as ve:
        config.logger.error(msg=f"Schema validation error: {ve}")
        return None

    for station in payload.data:
        if station.code == station_code.upper():
            return station.nlc

    config.logger.error(msg=f"No matching station for code: {station_code}")
    return None
