"""Builds the two SYNTHETIC Week 3 extraction fixtures from a REAL saved IIT Bombay detail page.

The saved pages (fixtures/week3/iitb_events/detail/) contain no event with two people in one field and no
"Organized by:" organization line, both of which Section 5 requires. Each synthetic page is the real
seminar-cum-workshop page with only its title and the body's <p><strong>Speaker:</strong> ...</p> paragraph
replaced, so the markup around it is the site's real markup. Names are fictional (the Section 7 fixture names).

    venv\\Scripts\\python scripts/make_week3_synthetic_fixtures.py
"""

from pathlib import Path

DETAIL = Path(__file__).resolve().parent.parent / "fixtures" / "week3" / "iitb_events" / "detail"
TEMPLATE = DETAIL / "seminar-cum-workshop-staggered-difference-differences-designs.html"
REAL_LINE = ("<p><strong>Speaker:</strong> Prof. Partha Deb, Professor of Economics, Hunter College, "
             "City University of New York</p>")
NOTE = "<!-- SYNTHETIC fixture: real page, Speaker paragraph replaced (scripts/make_week3_synthetic_fixtures.py) -->\n"

TITLE = "Seminar-cum-Workshop on Staggered Difference-in-Differences Designs"
VARIANTS = {
    "synthetic-two-speakers-and-organizers.html": ("SYNTHETIC Panel: Two Speakers and Organizers",
        "<p><strong>Speakers:</strong> Prof. Ananya Rao, Centre for Policy Research and Dr. Ravi Sen, "
        "Department of Economics, IIT Bombay</p>\n"
        "<p><strong>Organized by:</strong> Department of Economics, IIT Bombay and "
        "Centre for Policy Research (CPR)</p>\n"
        "<p><strong>Co-organized by:</strong> Department of Science and Technology</p>"),
    "synthetic-chair-moderator-host.html": ("SYNTHETIC Round Table: Chair, Moderator and Hosts",
        "<p><strong>Chair:</strong> Prof Ananya Rao</p>\n"
        "<p><strong>Moderator:</strong> A. Rao, CPR</p>\n"
        "<p><strong>Host:</strong> Smt. Meera Iyer &amp; Mr. Karan Shah</p>\n"
        "<p><strong>Speaker:</strong> Ananya R.</p>\n"
        "<p>Our distinguished guest Dr. Unlabelled Person will also address the gathering.</p>"),
}


def main() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    assert html.count(REAL_LINE) == 1, "template changed"
    assert html.count(TITLE) == 2, "template title changed"      # <title> and the article title field
    for name, (title, replacement) in VARIANTS.items():
        page = html.replace(REAL_LINE, replacement).replace(TITLE, title)
        (DETAIL / name).write_text(NOTE + page, encoding="utf-8")
        print(f"wrote {DETAIL / name}")


if __name__ == "__main__":
    main()
