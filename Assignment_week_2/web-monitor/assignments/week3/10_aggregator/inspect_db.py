"""Week 3 Section 10: duplicate checks and a short inventory of an aggregator database (read-only).

    venv\\Scripts\\python -m assignments.week3.10_aggregator.inspect_db --db data/week3_demo.db [--source <name>]
"""

import argparse
import sys

from src.storage import query

DUPLICATE_CHECKS = {
    "records": "SELECT item_url, COUNT(*) FROM records GROUP BY item_url HAVING COUNT(*) > 1",
    "item_people": "SELECT item_url, person_id, role, COUNT(*) FROM item_people "
                   "GROUP BY item_url, person_id, role HAVING COUNT(*) > 1",
    "item_organizations": "SELECT item_url, organization_id, role, COUNT(*) FROM item_organizations "
                          "GROUP BY item_url, organization_id, role HAVING COUNT(*) > 1",
    "discovered_items": "SELECT discovered_url, COUNT(*) FROM discovered_items GROUP BY discovered_url HAVING COUNT(*) > 1",
    "people (normalized_name)": "SELECT normalized_name, COUNT(*) FROM people GROUP BY normalized_name HAVING COUNT(*) > 1",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True)
    parser.add_argument("--source", default=None)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    for name, sql in DUPLICATE_CHECKS.items():
        rows = query(args.db, sql)
        print(f"{sql};\n  -> {len(rows)} row(s){'' if not rows else ': ' + str(rows[:5])}")
    where = "WHERE source_name = ?" if args.source else ""
    params = (args.source,) if args.source else ()
    print("\nrecords:", query(args.db, f"SELECT COUNT(*) FROM records {where}", params)[0][0],
          "| by detail_fetch_status:", query(args.db, f"SELECT detail_fetch_status, COUNT(*) FROM records {where} "
                                                      "GROUP BY 1 ORDER BY 1", params))
    print("discovered_items by content_class / in_scope:",
          query(args.db, "SELECT content_class, in_scope, COUNT(*) FROM discovered_items GROUP BY 1, 2 ORDER BY 1, 2"))
    print("entities:", {t: query(args.db, f"SELECT COUNT(*) FROM {t}")[0][0]
                        for t in ("people", "organizations", "item_people", "item_organizations",
                                  "entity_alias_candidates")})
    print("runs:", query(args.db, "SELECT status, new_count, changed_count, unchanged_count, not_seen_count, "
                                  "failed_count, items_discovered, items_parsed FROM runs ORDER BY started_at, rowid"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
