"""
Type definitions for JSON Feed version 1.1
See https://jsonfeed.org/version/1.1
"""

from typing import TypeAlias, TypedDict

JSONFEED_VERSION_URL = "https://jsonfeed.org/version/1.1"


class JsonFeedAuthor(TypedDict, total=False):
    name: str
    url: str
    avatar: str


AuthorsList: TypeAlias = list[JsonFeedAuthor]


class JsonFeedItem(TypedDict, total=False):
    id: str  # required
    url: str
    title: str
    content_html: str
    content_text: str
    image: str
    date_published: str
    date_modified: str
    authors: AuthorsList


class JsonFeedTopLevel(TypedDict, total=False):
    title: str  # required
    items: list[JsonFeedItem]  # required
    version: str  # required
    home_page_url: str
    description: str
    favicon: str
    authors: AuthorsList
