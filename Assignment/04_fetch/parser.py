from bs4 import BeautifulSoup
import urllib.parse


def parse_events(html: str, base_url: str) -> list[dict]:
    """
    Parses IIT Bombay News records from the given HTML string.

    Args:
        html: The HTML content as a string.
        base_url: The base URL to use for resolving relative URLs.

    Returns:
        A list of dictionaries, each representing a news item.
    """

    # Convert the HTML string into a BeautifulSoup object
    soup = BeautifulSoup(html, 'html.parser')

    # Store all extracted news items
    events = []

    # Target all repeated news containers
    containers = soup.select(
        '.homepage-news .view-content .views-row'
    )

    # Add temporary debugging output
    print(f"DEBUG: Found {len(containers)} containers")
    if containers:
        print("DEBUG: First container HTML:")
        print(containers[0].prettify()[:500] + "...")

    # Loop through each news item
    for i, container in enumerate(containers):

        # 1. Extract Title
        title_tag = container.find(
            class_='news-card-title'
        )

        title = (
            title_tag.get_text(" ", strip=True)
            if title_tag
            else None
        )

        # 2. Extract URL and make it absolute
        link_tag = container.select_one(
            '.news-card-more a'
        )

        item_url = None

        if link_tag and link_tag.has_attr('href'):

            raw_url = link_tag['href'].strip()

            # Convert relative URL to absolute URL if necessary
            item_url = urllib.parse.urljoin(
                base_url,
                raw_url
            )

        # 3. Extract Date
        date_tag = container.select_one(
            '.news-card-date time'
        )

        date_raw = (
            date_tag.get_text(" ", strip=True)
            if date_tag
            else None
        )

        # 4. Extract machine-readable datetime
        date_datetime = (
            date_tag.get('datetime')
            if date_tag
            else None
        )

        # 5. Extract Image
        image_tag = container.select_one(
            '.views-field-field-media-image img'
        )

        image_url = None
        image_alt = None

        if image_tag:

            # Extract alt text
            image_alt = image_tag.get('alt')

            # Extract image source
            if image_tag.has_attr('src'):

                raw_image_url = image_tag['src'].strip()

                # Convert relative image URL to absolute URL
                image_url = urllib.parse.urljoin(
                    base_url,
                    raw_image_url
                )

        # 6. Extract raw text from the entire news container
        raw_text = container.get_text(
            " ",
            strip=True
        )

        if i == 0:
            print("DEBUG: First container extracted fields:")
            print(f"  Title found: {bool(title)}")
            print(f"  Link found: {bool(item_url)}")
            print(f"  Date found: {bool(date_raw)}")
            print(f"  Image found: {bool(image_url)}")

        # Append extracted news item to our list
        events.append({

            "title": title,

            "item_url": item_url,

            "date_raw": date_raw,

            "date_datetime": date_datetime,

            "image_url": image_url,

            "image_alt": image_alt,

            "raw_text": raw_text
        })


    return events