"""Central-aggregator pipeline (Week 3 Section 10), config-driven and generic.

run_aggregator(config, db_path, ...) for a source with "pipeline": "aggregator":

  source config -> discovery (src.discovery.discover: methods + URLs from the registry entry, client = Fetcher)
    -> scope (src.scope, inside discovery) -> dedup on the canonical URL (inside discovery)
    -> router before fetching (src.router: PDFs / external links are never detail-fetched as HTML)
    -> capped detail fetch (scope.max_detail_items, config.detail_limit) -> router again with the Content-Type
    -> adapter.parse_event_detail -> assemble_record + validate_record (src.schema)
    -> entity mentions (src.entities) -> ONE storage transaction: records + entity links + review queue +
       discovered_items (src.storage.store_records_detailed with extra_writes)
    -> not_seen_this_run -> run metrics (src.metrics: printed block, RUN_SUMMARY log line, runs-table columns)

The adapter supplies only LISTING_SELECTORS, parse_event_detail(html, item_url) -> {"fields", "people", "orgs",
"parse_warnings"} and optional TIMEZONE. The scheduler (src.scheduler) chooses this path from config.pipeline,
under the same lock, run row and RUN_START / RUN_END logging as Week 2.

A failed run raises AggregatorRunError carrying the run's summary (status=failed), so the scheduler can store and
print the metrics of a failed run too. Nothing is written to the data tables by a failed run (one transaction).
"""

import importlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from urllib.parse import urlsplit

from src import metrics as run_metrics
from src.discovery.discover import discover
from src.entities import mention_rows, org_match, person_match, review_pairs
from src.fetcher import Fetcher, FetchError
from src.logging_config import (log_detail_failure, log_failure, log_rediscovered, log_store, log_validate,
                                log_validation_failure, setup_logger)
from src.router import classify_with_reason, fetchable_as_html
from src.schema import assemble_record, validate_record
from src.scope import ScopeConfig
from src.storage import (add_alias_candidates, count_not_seen, init_entity_tables, last_runs, list_entities,
                         store_records_detailed, upsert_discovered_items, write_entity_links)


class AggregatorRunError(RuntimeError):
    """A run-level failure (no discovery page fetched, empty listing, storage error). Carries the run summary."""

    def __init__(self, message: str, summary: dict):
        super().__init__(message)
        self.summary = summary


# -- entity write step (Sections 6-7) ---------------------------------------------------------------------------

def write_entities(conn: Any, links: dict, replace: Iterable[str] = ()) -> dict:
    """links = {item_url: (people_rows, org_rows)} (src.entities.mention_rows). Items in `replace` had their detail
    page parsed this run: their links are replaced; the others only gain missing links (storage.write_entity_links).
    Then every possible match is queued for review (entity_alias_candidates). Nothing is ever merged.
    Returns {"people_links", "organization_links", "review_candidates"} added this run."""
    replace = set(replace)
    added = {"people_links": 0, "organization_links": 0, "review_candidates": 0}
    for url, (people, orgs) in links.items():
        for key, n in write_entity_links(conn, url, people, orgs, replace=url in replace).items():
            added[key] += n
    added["review_candidates"] += add_alias_candidates(conn, "person",
                                                       review_pairs(list_entities(conn, "person"), person_match))
    added["review_candidates"] += add_alias_candidates(conn, "organization",
                                                       review_pairs(list_entities(conn, "organization"), org_match))
    return added


# -- routing (Section 8) ----------------------------------------------------------------------------------------

def route_candidate(candidate, router_cfg: Optional[dict], content_type: Optional[str] = None) -> tuple[str, str]:
    """(content_class, class_reason) for a discovery candidate; out-of-scope candidates are still classified so the
    discovered_items row says what they were."""
    return classify_with_reason(candidate.record, content_type=content_type,
                                category_label=candidate.category_label, cfg=router_cfg)


def discovered_item_row(candidate, content_class: str, class_reason: str) -> dict:
    """One discovered_items row (storage.upsert_discovered_items) for a candidate and its routing decision."""
    record = candidate.record
    return {"discovered_url": record.discovered_url, "source_name": record.source_name,
            "discovery_methods": list(candidate.discovery_methods), "discovered_title": record.discovered_title,
            "source_timestamp": record.source_timestamp, "source_timestamp_raw": record.source_timestamp_raw,
            "first_discovered_at": record.discovered_at, "last_discovered_at": record.discovered_at,
            "in_scope": candidate.in_scope, "scope_reason": candidate.scope_reason,
            "content_class": content_class, "class_reason": class_reason}


# -- the pipeline -------------------------------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scope_of(config) -> ScopeConfig:
    """The source's scope; without a scope block, only the listing URL's own host is in scope."""
    return ScopeConfig.from_dict(config.scope or {"allowed_hosts": [(urlsplit(config.listing_url).hostname or "")]})


def _router_cfg(config, scope: ScopeConfig) -> dict:
    cfg = dict(config.router or {})
    cfg.setdefault("hosts", list(scope.allowed_hosts))
    return cfg


def _listing_fields(candidate, adapter) -> dict:
    """What the listing alone says (used when the detail page is not fetched or failed)."""
    return {"title": candidate.record.discovered_title, "event_start": candidate.record.source_timestamp,
            "timezone": getattr(adapter, "TIMEZONE", None)}


def run_aggregator(config, db_path: str, logger: Optional[logging.Logger] = None, fetcher: Optional[Fetcher] = None,
                   run_id: Optional[str] = None, run_started_at: Optional[str] = None,
                   rediscovery_cutoff: Optional[str] = None) -> dict:
    logger = logger or setup_logger()
    run_started_at = run_started_at or _utc_now()
    adapter = importlib.import_module(config.adapter) if isinstance(config.adapter, str) else config.adapter
    fetcher = fetcher or Fetcher(timeout_s=config.timeout_s, delay_s=config.request_delay_s,
                                 logger=logger.getChild("fetcher"), ca_bundle=config.ca_bundle)
    scope = scope_of(config)
    router_cfg = _router_cfg(config, scope)
    previous_run = next(iter(last_runs(db_path, source_id=config.source_id, status="success")), None)
    previous = run_metrics.summary_from_run(previous_run) if previous_run else None
    t_start = time.perf_counter()
    stats = {"pages_fetched": 0, "http_status": None, "items_discovered": 0}

    def fail(message: str, stage: str, error: Exception) -> AggregatorRunError:
        log_failure(logger, source_id=config.source_id, url=config.listing_url, stage=stage, error=error)
        summary = run_metrics.build_summary(source=config.source_id, status="failed", run_id=run_id, **stats,
                                            error=f"{type(error).__name__}: {error}")
        run_metrics.emit(summary, logger, previous)
        return AggregatorRunError(message, summary)

    # 1-3. DISCOVERY (+ scope + dedup on the canonical URL)
    try:
        found = discover(config, fetcher, logger, discovered_at=run_started_at)
    except FetchError as e:
        stats["http_status"] = e.status
        raise fail(f"every discovery page failed: {e}", "fetch", e) from e
    except Exception as e:
        raise fail(f"discovery failed: {e}", "parse", e) from e
    stats.update(pages_fetched=found.pages_fetched, http_status=found.http_status,
                 items_discovered=len(found.candidates))
    if not found.candidates and not config.allow_empty_listing:
        from src.runner import EmptyListingError
        error = EmptyListingError("discovery returned HTTP 200 but found 0 items: possible silent layout change "
                                  "(set allow_empty_listing to accept this)")
        raise fail(str(error), "parse", error)

    # 4. ROUTE before fetching; pick the capped detail targets (page order)
    routes = {c.url: route_candidate(c, router_cfg) for c in found.candidates}
    events = [c for c in found.candidates if c.in_scope and routes[c.url][0] == "event"]
    detail_cap = min(scope.max_detail_items, config.detail_limit) if config.supports_detail else 0
    targets = events[:detail_cap]

    # 5. DETAIL fetch + route again with the Content-Type + parse
    detail_logger = logger.getChild("detail")
    parsed: dict = {}            # url -> adapter result
    provenance: dict = {}        # url -> detail_* fields
    detail_failures = parse_failures = 0
    for candidate in targets:
        url = candidate.url
        try:
            response = fetcher.get(url)
        except FetchError as e:
            detail_failures += 1
            log_detail_failure(detail_logger, source_id=config.source_id, item_url=url, status=e.status, error=e)
            provenance[url] = {"detail_fetch_status": "failed", "detail_http_status": e.status,
                               "detail_fetched_at": _utc_now(), "detail_error": f"{e.error_type}: {e.reason}"}
            continue
        provenance[url] = {"detail_fetch_status": "ok", "detail_http_status": response.status,
                           "detail_fetched_at": response.fetched_at}
        routes[url] = route_candidate(candidate, router_cfg, content_type=response.content_type)
        if not fetchable_as_html(routes[url][0]) or routes[url][0] != "event":
            continue     # e.g. application/pdf: never parsed as HTML, not an event record
        try:
            parsed[url] = adapter.parse_event_detail(response.text, url)
        except Exception as e:
            parse_failures += 1
            log_detail_failure(detail_logger, source_id=config.source_id, item_url=url, status=response.status, error=e)
            provenance[url] = {"detail_fetch_status": "failed", "detail_http_status": response.status,
                               "detail_fetched_at": response.fetched_at, "detail_error": f"{type(e).__name__}: {e}"}

    # 6. NORMALIZE + ASSEMBLE + VALIDATE (every in-scope event; listing data when there is no parsed detail)
    valid, invalid, links, unparsed, parsed_records = [], [], {}, {}, []
    for candidate in events:
        url = candidate.url
        if routes[url][0] != "event":
            continue
        detail = parsed.get(url)
        merged = {"item_url": url, "fetched_at": candidate.record.discovered_at, "http_status": found.http_status,
                  "detail_fetch_status": "not_attempted", **provenance.get(url, {})}
        fields = _listing_fields(candidate, adapter)
        if detail is not None:
            fields.update({k: v for k, v in detail["fields"].items() if v not in (None, "", [])})
            if detail.get("parse_warnings"):
                unparsed[url] = set(detail["parse_warnings"])
        fields["extras"] = {**(fields.get("extras") or {}), "discovery_methods": list(candidate.discovery_methods),
                            "found_on": list(candidate.found_on),
                            "listing_timestamp_raw": candidate.record.source_timestamp_raw}
        record = assemble_record(config, merged, fields)
        errors = validate_record(record)
        if errors:
            invalid.append({"item_url": url, "errors": errors})
            log_validation_failure(logger, source_id=config.source_id, item_url=url, errors=errors)
            continue
        valid.append(record)
        if detail is not None:
            parsed_records.append(record)
            links[url] = mention_rows(detail["people"], detail["orgs"])
    log_validate(logger, valid=len(valid), invalid=len(invalid))
    people_extracted = sum(len(people) for people, _ in links.values())
    orgs_extracted = sum(len(orgs) for _, orgs in links.values())

    stats.update(items_parsed=len(parsed_records), parse_failures=parse_failures, detail_failures=detail_failures,
                 invalid=len(invalid), people_extracted=people_extracted, organizations_extracted=orgs_extracted)

    # 7. STORE: records + entity links + review queue + discovered_items, ONE transaction
    rows = [discovered_item_row(c, *routes[c.url]) for c in found.candidates]
    init_entity_tables(db_path)
    written: dict = {}

    def extra_writes(conn) -> None:
        written.update(write_entities(conn, links, replace=links))
        written["discovered_items"] = upsert_discovered_items(conn, rows)

    try:
        stored = store_records_detailed(db_path, valid, unparsed_fields=unparsed, now_iso=run_started_at,
                                        rediscovery_cutoff=rediscovery_cutoff, extra_writes=extra_writes)
        not_seen = count_not_seen(db_path, config.source_id, run_started_at)
    except Exception as e:
        raise fail(f"storage failed: {e}", "store", e) from e
    for url in stored.rediscovered:
        log_rediscovered(logger, config.source_id, url, stored.states[url], run_id)
    log_store(logger, new_count=stored.counts["new"], unchanged_count=stored.counts["unchanged"],
              changed_count=stored.counts["changed"], not_seen_count=not_seen, run_id=run_id)
    logger.info("ENTITIES run_id=%s source_id=%s people_extracted=%d organizations_extracted=%d people_links_added=%d "
                "organization_links_added=%d review_candidates_added=%d discovered_items_written=%d",
                run_id or "none", config.source_id, people_extracted, orgs_extracted, written["people_links"],
                written["organization_links"], written["review_candidates"], written["discovered_items"])

    # 8. METRICS
    summary = run_metrics.build_summary(source=config.source_id, status="success", run_id=run_id, **stats,
                                        counts=stored.counts, not_seen_this_run=not_seen, parsed_records=parsed_records)
    warnings = run_metrics.emit(summary, logger, previous)
    detail_status = {"ok": len(parsed), "failed": detail_failures + parse_failures,
                     "not_attempted": len(events) - len(targets)}
    return {"status": "success", "source_id": config.source_id, "counts": stored.counts,
            "not_seen_this_run": not_seen, "rediscovered": stored.rediscovered, "detail_status": detail_status,
            "records": valid, "invalid": invalid, "summary": summary, "coverage_warnings": warnings,
            "routes": routes, "pages_crawled": found.pages_fetched,
            "duration_ms": int((time.perf_counter() - t_start) * 1000)}
