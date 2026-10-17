"""Week 3 config keys (generic change G2): optional, validated, and inert for Week 2 listing sources."""

import pytest

from src.config import SourceConfig, load_source_configs


def make(**kw):
    base = dict(source_id="s", institution="X", adapter="a", listing_url="https://x.org/")
    return SourceConfig(**{**base, **kw})


def test_defaults_keep_a_week2_source_unchanged():
    config = make()
    assert config.pipeline == "listing" and config.discovery_methods() == ()
    assert config.scope is None and config.router is None and config.discovery_urls is None


def test_aggregator_needs_known_discovery_methods():
    assert make(pipeline="aggregator", discovery="html").discovery_methods() == ("html",)
    assert make(pipeline="aggregator", discovery=["html", "rss"]).discovery_methods() == ("html", "rss")
    for bad in (None, [], "json", ["html", "csv"]):
        with pytest.raises(ValueError, match="discovery must be"):
            make(pipeline="aggregator", discovery=bad)


def test_unknown_pipeline_rejected():
    with pytest.raises(ValueError, match="pipeline must be"):
        make(pipeline="crawler")


def test_every_configured_source_still_loads():
    configs = load_source_configs()
    assert configs["iit_bombay_hss_seminars"].pipeline == "listing"
