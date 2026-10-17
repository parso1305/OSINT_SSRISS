"""Generic HTML listing discovery, driven by a selector config. Takes HTML text; never fetches.

Only links INSIDE an item container become records. Navigation, header, footer and social links are never
item containers, so they never become records, however many links the page has. The selector values for a
real source live in its adapter (sources/<name>.py, LISTING_SELECTORS), never here.

HtmlListingConfig
  item        CSS selector for one item container (required), e.g. ".homepage-events .views-row"
  link        CSS selector, inside the item, for the item's link (default: the first a[href])
  title       CSS selector for the title text (default: the link's text)
  date        CSS selector for the item's date element (optional)
  date_attr   read the date from this attribute (e.g. "datetime") instead of the element text
  category    CSS selector for a category label shown on the card (optional; used by the router)
  utc_offset  the source's fixed UTC offset for dates written without one (e.g. "+05:30")
"""

from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from src.discovery.record import DiscoveryRecord, make_record, utc_now
from src.discovery.timestamps import to_utc_z


@dataclass(frozen=True)
class HtmlListingConfig:
    item: str
    link: str = "a[href]"
    title: Optional[str] = None
    date: Optional[str] = None
    date_attr: Optional[str] = None
    category: Optional[str] = None
    utc_offset: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "HtmlListingConfig":
        return cls(**data)


@dataclass(frozen=True)
class HtmlListingItem:
    record: DiscoveryRecord
    category_label: Optional[str]


def _text(node) -> Optional[str]:
    if node is None:
        return None
    return " ".join(node.get_text(" ", strip=True).split()) or None


def parse_listing_items(html: str, page_url: str, config: HtmlListingConfig, source_name: str,
                        discovered_at: Optional[str] = None) -> list[HtmlListingItem]:
    """Every item container with a resolvable http(s) link becomes one item (in page order)."""
    discovered_at = discovered_at or utc_now()
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for container in soup.select(config.item):
        link = container.select_one(config.link)
        if link is None or not link.get("href"):
            continue
        title_node = container.select_one(config.title) if config.title else link
        date_raw = None
        if config.date:
            date_node = container.select_one(config.date)
            if date_node is not None:
                date_raw = date_node.get(config.date_attr) if config.date_attr else _text(date_node)
        category = _text(container.select_one(config.category)) if config.category else None
        record = make_record(source_name, link["href"], page_url, "html", _text(title_node),
                             to_utc_z(date_raw, config.utc_offset), date_raw, discovered_at)
        if record is not None:
            items.append(HtmlListingItem(record=record, category_label=category))
    return items


def html_records(html: str, page_url: str, config: HtmlListingConfig, source_name: str,
                 discovered_at: Optional[str] = None) -> list[DiscoveryRecord]:
    return [i.record for i in parse_listing_items(html, page_url, config, source_name, discovered_at)]
