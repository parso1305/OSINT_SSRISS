"""Part 7: run the REAL generic scheduler/runner over the two sandbox adapters, on saved fixtures, into a temp DB.

Nothing under src/ is imported for modification; only the sandbox config (config/sources.json in this folder)
is copied with listing_url pointed at a local static server that replays the fixtures.
Output: logs/after_fixes/generalization_run.log (pipeline log) + logs/after_fixes/generalization_report.json.
The original audit run (2026-09-26) is in logs/generalization_run.log and logs/generalization_report.json.
"""

import hashlib
import json
import logging
import sqlite3
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parents[1]          # assignments/week2_audit
PROJECT_ROOT = AUDIT_DIR.parents[1]                      # web-monitor
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_source_configs, load_adapter  # noqa: E402
from src.enrich import merge_listing_and_detail  # noqa: E402
from src.logging_config import KeyValueFormatter  # noqa: E402
from src.scheduler import run_once  # noqa: E402
from src.schema import assemble_record, validate_record, CONTENT_FIELDS  # noqa: E402
from src.storage import list_runs  # noqa: E402

FIX = AUDIT_DIR / "fixtures"
ROUTES = {"/events": FIX / "me_iitb" / "listing.html", "/activities/": FIX / "cmi" / "listing.html"}
for f in (FIX / "me_iitb" / "detail").glob("*.html"):
    ROUTES["/event/" + f.stem.split("__event__", 1)[1]] = f


class Handler(BaseHTTPRequestHandler):
    requests: list[str] = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Handler.requests.append(self.path)
        if self.path == "/activities":
            # Reproduces the live server exactly: GET https://www.cmi.ac.in/activities -> 301 .../activities/
            # (checked 2026-09-26T13:53:22Z, see logs/live_urls.tsv)
            self.send_response(301)
            self.send_header("Location", "/activities/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        f = ROUTES.get(self.path)
        body = f.read_bytes() if f else b"<html><body>not saved as fixture</body></html>"
        self.send_response(200 if f else 404)
        self.send_header("Content-Type", "text/html; charset=UTF-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def src_hashes() -> dict:
    return {str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in ("src", "sources", "config") for p in sorted((PROJECT_ROOT / d).rglob("*")) if p.is_file()
            and "__pycache__" not in p.parts}


def main() -> None:
    before = src_hashes()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    tmp = Path(tempfile.mkdtemp(prefix="audit_gen_"))
    cfg_data = json.loads((AUDIT_DIR / "config" / "sources.json").read_text(encoding="utf-8"))
    for e in cfg_data["sources"]:
        if e["source_id"] in ("iit_bombay_me_events", "cmi_seminars"):
            e["listing_url"] = base + ("/events" if e["source_id"] == "iit_bombay_me_events" else "/activities/")
            e["request_delay_s"] = 0
    # config-only reuse check: the unchanged IIT Bombay HSS adapter pointed at the ME listing
    reuse = dict(next(e for e in cfg_data["sources"] if e["source_id"] == "iit_bombay_me_events"),
                 source_id="me_with_hss_adapter", adapter="sources.iit_bombay")
    cfg_data["sources"].append(reuse)
    cfg_path = tmp / "sources.json"
    cfg_path.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")
    db = str(tmp / "generalization.db")

    log_path = AUDIT_DIR / "logs" / "after_fixes" / "generalization_run.log"
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(KeyValueFormatter())
    logger = logging.getLogger("web_monitor")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    results = run_once(cfg_path, db, tmp / "locks", source_ids=["iit_bombay_me_events", "cmi_seminars", "me_with_hss_adapter"],
                       force=True, logger=logger)
    server.shutdown()

    report = {"base": base, "db": db, "config": str(cfg_path), "results": results, "runs": list_runs(db),
              "server_requests": Handler.requests, "sources": {}}
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    configs = load_source_configs(cfg_path)
    for sid in ("iit_bombay_me_events", "cmi_seminars"):
        rows = [dict(r) for r in conn.execute("SELECT * FROM records WHERE source_id = ? ORDER BY starts_at DESC", (sid,))]
        for r in rows:
            r["speakers"], r["extras"] = json.loads(r["speakers"]), json.loads(r["extras"])
            r["is_online"] = None if r["is_online"] is None else bool(r["is_online"])
        fill = {f: sum(1 for r in rows if r.get(f) not in (None, "", [])) for f in CONTENT_FIELDS}
        report["sources"][sid] = {
            "rows": len(rows), "validation_errors": {r["item_url"]: validate_record(r) for r in rows if validate_record(r)},
            "field_fill": fill, "sample": rows[:3],
            "status_counts": {s: sum(r["detail_fetch_status"] == s for r in rows) for s in ("ok", "failed", "not_attempted")},
        }
    conn.close()

    # The 3 saved ME detail pages through the generic merge + adapter.normalize + assemble_record path
    me_cfg = configs["iit_bombay_me_events"]
    me = load_adapter(me_cfg.adapter, supports_detail=True)
    listing = {i["item_url"].rsplit("/", 1)[-1]: i for i in me.parse_listing(ROUTES["/events"].read_text(encoding="utf-8"), base + "/events")}
    enriched = []
    for path, f in ROUTES.items():
        if path.startswith("/event/"):
            item = listing[path.rsplit("/", 1)[-1]]
            merged = dict(merge_listing_and_detail(item, me.parse_detail(f.read_text(encoding="utf-8"), item["item_url"])),
                          detail_fetch_status="ok")
            rec = assemble_record(me_cfg, merged, me.normalize(merged))
            enriched.append({"record": rec, "errors": validate_record(rec)})
    report["me_enriched_via_generic_merge"] = enriched
    report["generic_files_unchanged"] = before == src_hashes()
    out = AUDIT_DIR / "logs" / "after_fixes" / "generalization_report.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("results", "generic_files_unchanged")}, indent=1, default=str))
    for sid, s in report["sources"].items():
        print(sid, "rows", s["rows"], "status", s["status_counts"], "invalid", len(s["validation_errors"]), "fill", s["field_fill"])


if __name__ == "__main__":
    main()
