from datetime import datetime

from app.types import CronQuery, SupportedQuery

from .types import JSONFEED_VERSION_URL, JsonFeedItem, JsonFeedTopLevel


def get_top_level_feed(
    query: SupportedQuery, feed_items: list[JsonFeedItem]
) -> JsonFeedTopLevel:
    title_strings: list[str] = [query.config.domain, query.journey]

    if isinstance(query, CronQuery):
        title_strings.append(query.job_str)

    base_url: str = query.config.base_url
    favicon_url: str = query.config.favicon_url

    json_feed: JsonFeedTopLevel = JsonFeedTopLevel(
        version=JSONFEED_VERSION_URL,
        items=feed_items,
        title=" - ".join(title_strings),
        home_page_url=base_url,
        favicon=favicon_url,
    )

    return json_feed


def generate_items(
    query: SupportedQuery, result_dict: dict[datetime, str | None]
) -> list[JsonFeedItem]:
    title_list: list[str] = [query.config.domain, query.journey]

    feed_items: list[JsonFeedItem] = []

    for _dt, fare_text in result_dict.items():
        if not fare_text:
            continue

        fare_timestamp: str = _dt.replace(tzinfo=None).isoformat(timespec="minutes")
        item_title_text: list[str] = title_list + [fare_timestamp]
        published_timestamp: str = (
            datetime.now().replace(microsecond=0).isoformat(sep="T")
        )

        item_link_url: str = query.config.base_url

        feed_item: JsonFeedItem = JsonFeedItem(
            id=published_timestamp,
            url=item_link_url,
            title=" - ".join(item_title_text),
            content_text=fare_text,
            content_html=fare_text,
            date_published=published_timestamp,
        )

        feed_items.append(feed_item)

    return feed_items
