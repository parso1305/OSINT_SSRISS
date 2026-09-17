"""Unit tests for IIT Bombay fixtures, parser, normalizer, and storage."""

from pathlib import Path
import pytest

from sources.iit_bombay import parse_events, StructuralError
from src.schema import normalize_event, normalize_events
from src.storage import init_db, store_event, count_items

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "iit_bombay"


def load_fixture(filename: str) -> str:
    """Reads fixture HTML from fixtures/iit_bombay/."""
    file_path = FIXTURES_DIR / filename
    return file_path.read_text(encoding="utf-8")


def test_parse_expected_number_of_items():
    """Verify that parsing normal_page.html returns the exact expected number of cards (3)."""
    html = load_fixture("normal_page.html")
    events = parse_events(html)
    assert len(events) == 3


def test_parse_title():
    """Verify event title parsing and whitespace handling."""
    html = load_fixture("normal_page.html")
    events = parse_events(html)
    assert events[0]["title"] == "Annual Research & Innovation Symposium 2026"
    assert events[1]["title"] == "Distinguished Lecture on Quantum Information Systems"
    assert events[2]["title"] == "National Workshop on Ethical AI in Healthcare"


def test_parse_url():
    """Verify relative URL resolution to canonical absolute URL."""
    html = load_fixture("normal_page.html")
    events = parse_events(html, base_url="https://www.iitb.ac.in")
    assert events[0]["item_url"] == "https://www.iitb.ac.in/event/annual-research-symposium-2026"
    assert events[1]["item_url"] == "https://www.iitb.ac.in/event/quantum-computing-lecture"
    assert events[2]["item_url"] == "https://www.iitb.ac.in/event/ai-ethics-workshop"


def test_missing_optional_field():
    """Verify parsing handles omitted optional fields (venue, description) gracefully without failing."""
    html = load_fixture("missing_optional_field.html")
    events = parse_events(html)
    assert len(events) == 2

    # First event has description but no venue
    assert events[0]["title"] == "Student Robotics Club Orientation"
    assert events[0]["venue"] is None
    assert events[0]["description"] == "Welcome session and mechanical design intro for incoming undergraduate cohorts."

    # Second event has neither venue nor description
    assert events[1]["title"] == "Aerospace Engineering Department Colloquium"
    assert events[1]["venue"] is None
    assert events[1]["description"] is None


def test_empty_listing():
    """Verify valid listing container with 0 items returns an empty list without error."""
    html = load_fixture("empty_listing.html")
    events = parse_events(html)
    assert events == []


def test_normalization_shape():
    """Verify that normalized record adheres to the expected schema shape and types."""
    html = load_fixture("normal_page.html")
    raw_events = parse_events(html)
    normalized = normalize_event(raw_events[0], base_url="https://www.iitb.ac.in")

    expected_keys = {
        "title",
        "item_url",
        "date_raw",
        "published_at",
        "venue",
        "description",
        "raw_text"
    }
    assert set(normalized.keys()) == expected_keys
    assert normalized["title"] == "Annual Research & Innovation Symposium 2026"
    assert normalized["item_url"] == "https://www.iitb.ac.in/event/annual-research-symposium-2026"
    assert normalized["published_at"] == "2026-10-15"
    assert normalized["venue"] == "PC Saxena Auditorium"
    assert isinstance(normalized["raw_text"], str)


def test_duplicate_item(tmp_path):
    """
    Verify that inserting the same record twice through the full normalize -> store pipeline
    does not increase the database row count (deduplication on canonical URL).
    """
    db_file = str(tmp_path / "test_events.db")
    init_db(db_file)

    html = load_fixture("normal_page.html")
    raw_events = parse_events(html)
    normalized_item = normalize_event(raw_events[0], base_url="https://www.iitb.ac.in")

    # First store pass
    status_1 = store_event(db_file, normalized_item)
    assert status_1 == "new"
    assert count_items(db_file) == 1

    # Second store pass with identical record
    status_2 = store_event(db_file, normalized_item)
    assert status_2 == "existing"
    assert count_items(db_file) == 1  # Row count MUST NOT grow


def test_changed_card_structure_fails_loudly():
    """Verify that redesigned markup raises StructuralError instead of returning empty results."""
    html = load_fixture("changed_card_structure.html")
    with pytest.raises(StructuralError) as exc_info:
        parse_events(html)
    assert "Structural layout mismatch" in str(exc_info.value)


def test_structured_logging_pipeline(tmp_path):
    """Verify structured logging keys and format in successful run."""
    import io
    import logging
    from src.logging_config import KeyValueFormatter
    from src.runner import run_pipeline

    stream = io.StringIO()
    logger = logging.getLogger("test_logger_success")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger.addHandler(handler)
    logger.propagate = False

    db_file = str(tmp_path / "pipeline_test.db")
    html = load_fixture("normal_page.html")

    result = run_pipeline(
        source_name="iit_bombay",
        url="https://www.iitb.ac.in/events",
        db_path=db_file,
        html_override=html,
        logger=logger
    )
    assert result["status"] == "success"

    output = stream.getvalue()
    assert "START source=iit_bombay" in output
    assert "FETCH url=https://www.iitb.ac.in/events status=200 duration_ms=" in output
    assert "PARSE records=3" in output
    assert "NORMALIZE records=3" in output
    assert "STORE new=3 existing=0 changed=0" in output
    assert "END duration_ms=" in output


def test_structured_logging_empty_listing_warning(tmp_path):
    """Verify that empty listing logs WARNING and does not crash."""
    import io
    import logging
    from src.logging_config import KeyValueFormatter
    from src.runner import run_pipeline

    stream = io.StringIO()
    logger = logging.getLogger("test_logger_empty")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger.addHandler(handler)
    logger.propagate = False

    db_file = str(tmp_path / "empty_pipeline.db")
    html = load_fixture("empty_listing.html")

    result = run_pipeline(
        source_name="iit_bombay",
        url="https://www.iitb.ac.in/events",
        db_path=db_file,
        html_override=html,
        logger=logger
    )
    assert result["status"] == "success"

    output = stream.getvalue()
    assert "[WARNING] WARNING source=iit_bombay" in output
    assert "PARSE records=0" in output
    assert "STORE new=0 existing=0 changed=0" in output

