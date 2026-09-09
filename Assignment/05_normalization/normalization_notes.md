# Normalization Notes

1. **Date format and date normalization**:
   Based on the data, the extracted date in `date_raw` is in the format `DD Mon YYYY` (e.g., "03 Sep 2026"). I assume this format is consistent across IIT Bombay news entries. The normalizer parses this format safely and produces an ISO-style `YYYY-MM-DD` string in a new `published_at` field. If the date is missing or parsing fails, the program safely falls back to `None` and does not crash.

2. **Missing optional fields**:
   It is assumed that while every item dictionary exists, some of its keys might hold empty or missing data. Missing optional data (like missing `image_url` or `image_alt`) is handled defensively using `.get()` and evaluating to `None` in the normalized output, preventing `KeyError`.

3. **URL construction / canonical URLs**:
   The raw `item_url` and `image_url` extracted from the HTML can be relative. We assume `https://www.iitb.ac.in` is the correct canonical base URL. We use `urllib.parse.urljoin` to generate stable, absolute URLs and strip unnecessary surrounding whitespace from the raw string.

4. **Title whitespace cleanup**:
   It's assumed that the title's content matters, but multiple contiguous whitespace characters (including newlines and tabs) are an artifact of HTML parsing and do not carry semantic meaning. I apply a regex (`re.sub(r'\s+', ' ', raw_title)`) to collapse all inner whitespaces into a single space, and `.strip()` the ends.

5. **Image handling**:
   If an image tag is completely missing from an item, the scraper produces `None`. The normalization layer safely propagates this `None`. For `image_alt` text, I apply the same robust whitespace cleanup as the title, as alt texts can sometimes contain erratic spacing.

6. **Preservation of raw text / provenance**:
   The `raw_text` field contains the entirety of the scraped content in the item node. This is preserved in the normalized item for provenance purposes (in case we need to re-extract information that wasn't captured initially). The `date_raw` is also preserved untouched, in case our date parsing logic missed an edge case (e.g. "Recently").
