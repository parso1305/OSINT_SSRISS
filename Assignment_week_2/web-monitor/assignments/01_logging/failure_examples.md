# Section 1: Structured Failure Logging Examples

Regenerated 2026-09-26 20:14 UTC by `python scripts/failure_examples_run.py` from **real runs of the current code**: the real runner, Fetcher, adapter and SQLite, against the local fixture site (`scripts/fixture_site.py`, saved live HSS HTML) with one fault injected per case. Log lines are pasted verbatim (timestamps are local time; ports are random).

Format (`src/logging_config.py`): `YYYY-MM-DD HH:MM:SS [LEVEL] logger=<name> EVENT key=value …`. Logger names: `web_monitor` (run stages, FAILURE, WARNING, PARSE_WARNING, VALIDATION_FAILURE), `web_monitor.fetcher` (FETCH, FETCH_ERROR), `web_monitor.detail` (DETAIL_FAILURE). Every line carries the source (`source_id=`), the stage, and for failures the error type, so `grep` alone tells what failed where.

> The previous version of this file (2026-09-17) was captured before the Assignment 7 refactor: no `logger=` field, `source=iit_bombay` instead of `source_id=`, and a legacy fixture's container (`.view-events-listing`). It is in git history.

---

## Baseline: successful run

```text
2026-09-27 01:44:33 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:33 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51524/events/seminars-and-talks status=200 duration_ms=2
2026-09-27 01:44:33 [INFO] logger=web_monitor Page 1 yielded 10 items
2026-09-27 01:44:33 [INFO] logger=web_monitor PARSE records=10
2026-09-27 01:44:33 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51524/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability status=200 duration_ms=23
2026-09-27 01:44:33 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51524/events/seminar-talk/tracing-success-indian-democracy-success-nation-building status=200 duration_ms=20
2026-09-27 01:44:33 [INFO] logger=web_monitor ENRICH ok=2 failed=0 not_attempted=8
2026-09-27 01:44:33 [INFO] logger=web_monitor NORMALIZE records=10
2026-09-27 01:44:33 [INFO] logger=web_monitor VALIDATE valid=10 invalid=0
2026-09-27 01:44:33 [INFO] logger=web_monitor STORE new=10 existing=0 changed=0
2026-09-27 01:44:33 [INFO] logger=web_monitor END source_id=iit_bombay_hss_seminars duration_ms=153
```

---

## Case 1: Invalid listing URL

- **Stage**: `parse` (reported)
- **Severity**: `ERROR`, run aborts
- **Error type**: `EmptyListingError`
- **Cause**: `listing_url` is not a usable http(s) URL, so `resolve_item_url` returns `""` and **no request is made**. The run fails, which is correct. **The message is misleading**, though: it says "HTTP 200 … parsed 0 items" for a URL that was never fetched. Suggested fix (not applied: outside the agreed audit-fix list): reject such a `listing_url` when the config is loaded.

```text
2026-09-27 01:44:34 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:34 [INFO] logger=web_monitor PARSE records=0
2026-09-27 01:44:34 [ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars url=http:// stage=parse error_type=EmptyListingError message="Listing returned HTTP 200 but parsed 0 items: possible silent layout change (set allow_empty_listing to accept this)"
```

---

## Case 2: Connection failure

- **Stage**: `fetch`
- **Severity**: `ERROR`, run aborts
- **Error type**: `ConnectionError` (FETCH_ERROR), `FetchError` (FAILURE)
- **Cause**: Nothing listens on the port. The first request is robots.txt; RFC 9309 treats an unreachable robots.txt as "disallow all", so the run stops there. `FETCH_ERROR` names the underlying cause.

```text
2026-09-27 01:44:34 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:36 [WARNING] logger=web_monitor.fetcher FETCH_ERROR url=http://127.0.0.1:51529/robots.txt status=none error_type=ConnectionError message="robots.txt unreachable (ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=51529): Max retries exceeded with url: /robots.txt (Caused by NewConnectionError('HTTPConnection(host='127.0.0.1', port=51529): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it'))) for url: http://127.0.0.1:51529/events/seminars-and-talks"
2026-09-27 01:44:36 [ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars url=http://127.0.0.1:51529/events/seminars-and-talks stage=fetch error_type=FetchError message="robots.txt unreachable (ConnectionError: HTTPConnectionPool(host='127.0.0.1', port=51529): Max retries exceeded with url: /robots.txt (Caused by NewConnectionError('HTTPConnection(host='127.0.0.1', port=51529): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it'))) for url: http://127.0.0.1:51529/events/seminars-and-talks"
```

---

## Case 3: Site redesign (listing container renamed)

- **Stage**: `parse`
- **Severity**: `ERROR`, run aborts
- **Error type**: `StructuralError`
- **Cause**: The listing container `.view-seminars-and-talks .view-content` is gone. The adapter raises instead of returning an empty list; nothing is stored.

```text
2026-09-27 01:44:36 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:36 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51531/events/seminars-and-talks status=200 duration_ms=12
2026-09-27 01:44:36 [ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars url=http://127.0.0.1:51531/events/seminars-and-talks stage=parse error_type=StructuralError message="Structural layout mismatch: Target container '.view-seminars-and-talks .view-content' not found in HTML. Site structure may have changed."
```

---

## Case 4a: Empty listing (default: the run fails)

- **Stage**: `parse`
- **Severity**: `ERROR`, run aborts
- **Error type**: `EmptyListingError`
- **Cause**: The page loads (HTTP 200) and the container exists, but the card class was renamed, so 0 items parse. Since the audit fix this fails the run (scheduler: `status=failed`, exit code 1) before anything is stored; existing records are untouched.

```text
2026-09-27 01:44:36 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:36 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51534/events/seminars-and-talks status=200 duration_ms=15
2026-09-27 01:44:36 [INFO] logger=web_monitor Page 1 yielded 0 items
2026-09-27 01:44:36 [INFO] logger=web_monitor PARSE records=0
2026-09-27 01:44:36 [ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars url=http://127.0.0.1:51534/events/seminars-and-talks stage=parse error_type=EmptyListingError message="Listing returned HTTP 200 but parsed 0 items: possible silent layout change (set allow_empty_listing to accept this)"
```

---

## Case 4b: Empty listing on a source with allow_empty_listing: true

- **Stage**: `parse`
- **Severity**: `WARNING`, run continues
- **Error type**: none
- **Cause**: Same page, on a source configured with `allow_empty_listing: true` (a feed that may legitimately be empty).

```text
2026-09-27 01:44:36 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:36 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51534/events/seminars-and-talks status=200 duration_ms=15
2026-09-27 01:44:36 [INFO] logger=web_monitor Page 1 yielded 0 items
2026-09-27 01:44:36 [INFO] logger=web_monitor PARSE records=0
2026-09-27 01:44:36 [WARNING] logger=web_monitor WARNING source_id=iit_bombay_hss_seminars url=http://127.0.0.1:51534/events/seminars-and-talks stage=parse message="Listing returned HTTP 200 but parsed 0 items: possible silent layout change"
2026-09-27 01:44:36 [INFO] logger=web_monitor ENRICH ok=0 failed=0 not_attempted=0
2026-09-27 01:44:36 [INFO] logger=web_monitor NORMALIZE records=0
2026-09-27 01:44:36 [INFO] logger=web_monitor VALIDATE valid=0 invalid=0
2026-09-27 01:44:36 [INFO] logger=web_monitor STORE new=0 existing=0 changed=0
2026-09-27 01:44:36 [INFO] logger=web_monitor END source_id=iit_bombay_hss_seminars duration_ms=62
```

---

## Case 5: Database write problem

- **Stage**: `store`
- **Severity**: `ERROR`, run aborts
- **Error type**: `DatabaseError`
- **Cause**: The DB file is not an SQLite database. Fetch, parse, enrichment and validation succeed; storing fails and the transaction writes nothing.

```text
2026-09-27 01:44:37 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:37 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51539/events/seminars-and-talks status=200 duration_ms=1
2026-09-27 01:44:37 [INFO] logger=web_monitor Page 1 yielded 10 items
2026-09-27 01:44:37 [INFO] logger=web_monitor PARSE records=10
2026-09-27 01:44:37 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51539/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability status=200 duration_ms=24
2026-09-27 01:44:37 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51539/events/seminar-talk/tracing-success-indian-democracy-success-nation-building status=200 duration_ms=21
2026-09-27 01:44:37 [INFO] logger=web_monitor ENRICH ok=2 failed=0 not_attempted=8
2026-09-27 01:44:37 [INFO] logger=web_monitor NORMALIZE records=10
2026-09-27 01:44:37 [INFO] logger=web_monitor VALIDATE valid=10 invalid=0
2026-09-27 01:44:37 [ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars url=http://127.0.0.1:51539/events/seminars-and-talks stage=store error_type=DatabaseError message="file is not a database"
```

---

## Case 6: TLS certificate cannot be verified

- **Stage**: `fetch`
- **Severity**: `ERROR`, run aborts
- **Error type**: `SSLError` (FETCH_ERROR), `FetchError` (FAILURE)
- **Cause**: The server's certificate is self-signed. Verification is never switched off: the run fails. A source whose server omits an intermediate certificate gets a `ca_bundle` instead (README, TLS section).

```text
2026-09-27 01:44:37 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:38 [WARNING] logger=web_monitor.fetcher FETCH_ERROR url=https://127.0.0.1:51544/robots.txt status=none error_type=SSLError message="robots.txt unreachable (SSLError: HTTPSConnectionPool(host='127.0.0.1', port=51544): Max retries exceeded with url: /robots.txt (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1028)')))) for url: https://127.0.0.1:51544/events/seminars-and-talks"
2026-09-27 01:44:38 [ERROR] logger=web_monitor FAILURE source_id=iit_bombay_hss_seminars url=https://127.0.0.1:51544/events/seminars-and-talks stage=fetch error_type=FetchError message="robots.txt unreachable (SSLError: HTTPSConnectionPool(host='127.0.0.1', port=51544): Max retries exceeded with url: /robots.txt (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1028)')))) for url: https://127.0.0.1:51544/events/seminars-and-talks"
```

---

## Case 7: One detail page fails (non-aborting)

- **Stage**: `enrich` (per item)
- **Severity**: `WARNING`, run continues
- **Error type**: `FetchError` (DETAIL_FAILURE)
- **Cause**: One detail page answers 404. That item keeps its listing data (`detail_fetch_status=failed`); the other items are enriched and every record is stored.

```text
2026-09-27 01:44:38 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:38 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51546/events/seminars-and-talks status=200 duration_ms=19
2026-09-27 01:44:38 [INFO] logger=web_monitor Page 1 yielded 10 items
2026-09-27 01:44:38 [INFO] logger=web_monitor PARSE records=10
2026-09-27 01:44:38 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51546/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability status=200 duration_ms=24
2026-09-27 01:44:38 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51546/events/seminar-talk/tracing-success-indian-democracy-success-nation-building status=404 duration_ms=2
2026-09-27 01:44:38 [WARNING] logger=web_monitor.detail DETAIL_FAILURE source_id=iit_bombay_hss_seminars item_url=http://127.0.0.1:51546/events/seminar-talk/tracing-success-indian-democracy-success-nation-building status=404 error_type=FetchError message="HTTP 404 Not Found for url: http://127.0.0.1:51546/events/seminar-talk/tracing-success-indian-democracy-success-nation-building"
2026-09-27 01:44:38 [INFO] logger=web_monitor ENRICH ok=1 failed=1 not_attempted=8
2026-09-27 01:44:38 [INFO] logger=web_monitor NORMALIZE records=10
2026-09-27 01:44:38 [INFO] logger=web_monitor VALIDATE valid=10 invalid=0
2026-09-27 01:44:38 [INFO] logger=web_monitor STORE new=10 existing=0 changed=0
2026-09-27 01:44:38 [INFO] logger=web_monitor END source_id=iit_bombay_hss_seminars duration_ms=109
```

---

## Case 8: Date format changed on a detail page (non-aborting)

- **Stage**: `normalize` (per field)
- **Severity**: `WARNING`, run continues
- **Error type**: none (PARSE_WARNING)
- **Cause**: The detail page's `<time datetime>` is text instead of ISO 8601. The value counts as unknown: `starts_at` falls back to the listing date + time, `ends_at` keeps any stored value, and the change is logged instead of silently erasing data.

```text
2026-09-27 01:44:38 [INFO] logger=web_monitor START source_id=iit_bombay_hss_seminars
2026-09-27 01:44:38 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51551/events/seminars-and-talks status=200 duration_ms=22
2026-09-27 01:44:38 [INFO] logger=web_monitor Page 1 yielded 10 items
2026-09-27 01:44:38 [INFO] logger=web_monitor PARSE records=10
2026-09-27 01:44:38 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51551/events/seminar-talk/islands-tri-junction-fragility-and-vulnerability status=200 duration_ms=3
2026-09-27 01:44:38 [INFO] logger=web_monitor.fetcher FETCH url=http://127.0.0.1:51551/events/seminar-talk/tracing-success-indian-democracy-success-nation-building status=200 duration_ms=13
2026-09-27 01:44:38 [INFO] logger=web_monitor ENRICH ok=2 failed=0 not_attempted=8
2026-09-27 01:44:38 [WARNING] logger=web_monitor PARSE_WARNING source_id=iit_bombay_hss_seminars item_url=http://127.0.0.1:51551/events/seminar-talk/tracing-success-indian-democracy-success-nation-building field=starts_at raw="17 September 2025"
2026-09-27 01:44:38 [WARNING] logger=web_monitor PARSE_WARNING source_id=iit_bombay_hss_seminars item_url=http://127.0.0.1:51551/events/seminar-talk/tracing-success-indian-democracy-success-nation-building field=ends_at raw="17 September 2025"
2026-09-27 01:44:38 [INFO] logger=web_monitor NORMALIZE records=10
2026-09-27 01:44:38 [INFO] logger=web_monitor VALIDATE valid=10 invalid=0
2026-09-27 01:44:38 [INFO] logger=web_monitor STORE new=10 existing=0 changed=0
2026-09-27 01:44:38 [INFO] logger=web_monitor END source_id=iit_bombay_hss_seminars duration_ms=109
```
