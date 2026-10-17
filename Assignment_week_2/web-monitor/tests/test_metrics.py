"""Week 3 Section 9: run metrics. Healthy vs deliberately broken local fixtures, through the real scheduler path.

Each summary must make its failure visible and distinguishable from "nothing new"
(assignments/week3/09_metrics/failure_signatures.md).
"""

import importlib
import io
import socket
from contextlib import redirect_stdout

import pytest

from src import metrics
from src.storage import last_runs, list_runs

scenarios = importlib.import_module("assignments.week3.09_metrics.failure_signatures_run")


@pytest.fixture
def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run(tmp_path, db_name, port, broken=None, methods=("html", "rss")):
    return scenarios.scenario(str(tmp_path / f"{db_name}.db"), tmp_path / "locks", broken=broken, port=port,
                              methods=methods)


def block_values(text: str) -> dict:
    return {line.split(": ", 1)[0]: line.split(": ", 1)[1] for line in text.splitlines()
            if ": " in line and line.split(": ", 1)[0].isupper() and " " not in line.split(": ", 1)[0]}


def test_nothing_new_summary(tmp_path, port):
    first, _ = run(tmp_path, "healthy", port)
    second, text = run(tmp_path, "healthy", port)
    s = second["summary"]
    assert (s["items_discovered"], s["items_parsed"], s["new"], s["unchanged"], s["failed"]) == (25, 20, 0, 22, 0)
    assert s["http_status"] == 200 and s["status"] == "success"
    values = block_values(text)
    assert [k for k in values] == ["SOURCE", "STATUS", "PAGES_FETCHED", "ITEMS_DISCOVERED", "ITEMS_PARSED", "NEW",
                                   "CHANGED", "UNCHANGED", "NOT_SEEN_THIS_RUN", "FAILED", "PEOPLE_EXTRACTED",
                                   "ORGANIZATIONS_EXTRACTED"]
    assert values["NEW"] == "0" and values["UNCHANGED"] == "22" and values["ITEMS_PARSED"] == "20"
    assert "RUN_SUMMARY run_id=" in text and "new=0 changed=0 unchanged=22" in text


def test_broken_detail_parser_is_parsed_zero_not_nothing_new(tmp_path, port):
    result, text = run(tmp_path, "detail", port, broken="detail", methods=("html",))
    s = result["summary"]
    assert (s["items_discovered"], s["items_parsed"], s["parse_failures"], s["failed"]) == (25, 0, 20, 20)
    assert s["status"] == "success" and s["people_extracted"] == 0 and text.count("DETAIL_FAILURE") == 20


def test_broken_listing_selector_is_discovered_zero_with_http_200(tmp_path, port):
    result, text = run(tmp_path, "listing", port, broken="listing", methods=("html",))
    assert result["status"] == "failed" and "found 0 items" in result["error"]
    s = result["summary"]
    assert (s["status"], s["http_status"], s["items_discovered"], s["pages_fetched"]) == ("failed", 200, 0, 1)
    assert "DISCOVER_EMPTY" in text and block_values(text)["ITEMS_DISCOVERED"] == "0"


def test_http_failure_is_non_200(tmp_path, port):
    result, text = run(tmp_path, "http", port, broken="http", methods=("html",))
    s = result["summary"]
    assert (result["status"], s["http_status"], s["items_discovered"], s["pages_fetched"]) == ("failed", 503, 0, 0)
    assert "DISCOVER_FAILURE" in text and "status=503" in text


def test_failed_run_still_writes_its_summary_to_the_runs_row(tmp_path, port):
    run(tmp_path, "listing", port, broken="listing", methods=("html",))
    row = list_runs(str(tmp_path / "listing.db"))[-1]
    assert (row["status"], row["http_status"], row["items_discovered"], row["pages_fetched"]) == ("failed", 200, 0, 1)
    assert row["error"].startswith("AggregatorRunError")


def test_a_second_method_cannot_hide_a_broken_listing(tmp_path, port):
    result, text = run(tmp_path, "listing_rss", port, broken="listing", methods=("html", "rss"))
    assert result["status"] == "success" and result["summary"]["items_discovered"] == 3   # only the feed's items
    assert "DISCOVER_EMPTY source_id=local_aggregator_fixture method=html" in text


def test_coverage_drop_warning_even_when_counts_look_normal(tmp_path, port):
    run(tmp_path, "healthy", port)
    result, text = run(tmp_path, "healthy", port, broken="speaker_label")
    s = result["summary"]
    assert s["status"] == "success" and s["failed"] == 0 and s["items_parsed"] == 20
    assert "COVERAGE_DROP source=local_aggregator_fixture" in text and "metric=pct_with_speaker previous=65.0" in text
    assert "metric=pct_with_date" not in text                          # dates did not drop


def test_metrics_columns_on_the_runs_row(tmp_path, port):
    run(tmp_path, "healthy", port)
    row = last_runs(str(tmp_path / "healthy.db"))[0]
    assert (row["pages_fetched"], row["items_discovered"], row["items_parsed"], row["new_count"],
            row["people_extracted"], row["organizations_extracted"], row["pct_with_date"]) == (2, 25, 20, 22, 19, 3, 100.0)
    assert row["not_seen_count"] == 0 and row["parse_failures"] == 0 and row["detail_failures"] == 0


def test_cli_prints_the_last_summary(tmp_path, port):
    run(tmp_path, "healthy", port)
    out = io.StringIO()
    with redirect_stdout(out):
        assert metrics.main(["--last", "--db", str(tmp_path / "healthy.db"), "--source", "local_aggregator_fixture"]) == 0
    text = out.getvalue()
    assert "SOURCE: local_aggregator_fixture" in text and "ITEMS_DISCOVERED: 25" in text and "NEW: 22" in text
    with redirect_stdout(io.StringIO()):
        assert metrics.main(["--last", "--db", str(tmp_path / "healthy.db"), "--source", "nope"]) == 1


@pytest.mark.parametrize("before, now, warns", [(80.0, 0.0, True), (80.0, 50.0, True), (80.0, 51.0, False),
                                                (20.0, 0.0, False), (None, 0.0, False)])
def test_coverage_threshold(before, now, warns):
    previous = {"items_parsed": 10, "pct_with_speaker": before, "run_id": "p"}
    current = {"items_parsed": 10, "pct_with_speaker": now, "source": "s"}
    assert bool(metrics.coverage_warnings(current, previous)) is warns
