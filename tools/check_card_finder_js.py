#!/usr/bin/env python3
"""
Behaviour of card-finder.js in a real browser, on a fixture page built by
the real generators (tools/card_finder.py, tools/breach_industries.py).

The search box, the industry buttons, synonyms and the skipped label can only
be checked by running the script, so run this after any change to
card-finder.js or to what the generators render into the finder:

    python3 tools/check_card_finder_js.py     # exit 0 when every check passes

It needs a Python with Playwright and its Chromium installed (the image
generators use the same). It is not run in CI.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from breach_industries import render_line, synonym_map  # noqa: E402
from card_finder import Entry, render_finder  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("check_card_finder_js.py needs Playwright: run it with a Python that has it installed")

# (id, title, industries). c4, c7 and c8 carry words that a loose match would
# confuse with an industry: "cryptographically", "legal staff", "flaw",
# "bank" in prose. c6 is tagged Hospitality, which contains "hospital".
CARDS = [("c1", "Alpha Bank Heist", ["Finance"]), ("c2", "Beta Clinic", ["Finance", "Healthcare"]),
         ("c3", "Gamma Tools", ["Technology"]), ("c4", "Delta cryptographically signed", ["Technology"]),
         ("c5", "Epsilon Wallet", ["Crypto"]), ("c6", "Zeta Hospitality Group", ["Hospitality"]),
         ("c7", "Eta flaw seen by legal staff", ["Technology"]),
         ("c8", "Theta bank statement export", ["Technology"])]
ALL = [c for c, _, _ in CARDS]
BASE = "http://t.test"


def fixture_page() -> str:
    finder = "\n".join(render_finder(
        [Entry(c, t, "2026") for c, t, _ in CARDS], input_id="q", id_prefix="ix", label="Search",
        placeholder="Search", index_label="Index", noun="card", nouns="cards",
        text_selector=".t, .industries-hit",
        filters=["Crypto", "Finance", "Healthcare", "Hospitality", "Technology"],
        filter_label="Industries", synonyms=synonym_map(), filter_selector=".industries-hit"))
    # The skipped "slides" span is a searched node that is itself skipped,
    # as the deck page's slide-count tag is.
    cards = "".join(f'<li class="card" id="{c}"><h2 class="t">{t}</h2>{render_line(i)}'
                    f'<span class="t" data-finder-skip>slides</span></li>' for c, t, i in CARDS)
    # The charset matters: card-finder.js holds literal combining marks.
    return ('<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/style.css">'
            f'</head><body>{finder}<ul>{cards}</ul><script src="/card-finder.js"></script></body></html>')


def main() -> int:
    page_html = fixture_page()
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)

    def handler(route) -> None:
        path = route.request.url[len(BASE):].split("?")[0]
        if path == "/":
            route.fulfill(status=200, content_type="text/html", body=page_html)
            return
        f = ROOT / path.lstrip("/")
        if not f.is_file():
            route.fulfill(status=404, body=b"")
            return
        types = {".css": "text/css", ".js": "text/javascript"}
        route.fulfill(status=200, content_type=types.get(f.suffix, "application/octet-stream"),
                      body=f.read_bytes())

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.route(f"{BASE}/**", handler)
        pg.goto(f"{BASE}/")

        def shown() -> list[str]:
            return pg.eval_on_selector_all(".card", "cs => cs.filter(c => !c.classList.contains('is-hidden'))"
                                                    ".map(c => c.id)")

        def pressed() -> list[str]:
            return pg.eval_on_selector_all("[data-finder-query]", "bs => bs.filter(b => b.getAttribute("
                                           "'aria-pressed') === 'true').map(b => b.dataset.finderQuery)")

        def val() -> str:
            return pg.input_value("#q")

        def btn(name: str):
            return pg.locator(f'[data-finder-query="{name}"]')

        def type_(s: str) -> None:
            pg.fill("#q", s)
            pg.wait_for_timeout(250)  # past the script's 100ms debounce

        def key(k: str, where: str | None = None) -> None:
            if where:
                pg.press(where, k)
            else:
                pg.keyboard.press(k)
            pg.wait_for_timeout(150)

        expect(pg.locator(".card-finder-btn").count() == 5, "five buttons rendered")
        expect(pressed() == [], "no button pressed on load")
        type_("alpha")
        expect(shown() == ["c1"], "plain search still works")
        type_("")
        btn("Finance").click()
        expect(val() == "Finance" and shown() == ["c1", "c2"] and pressed() == ["Finance"],
               "a button fills the field, filters, and is pressed")
        btn("Healthcare").click()
        expect(val() == "Healthcare" and shown() == ["c2"] and pressed() == ["Healthcare"],
               "a second button replaces the first; only it is pressed")
        btn("Healthcare").click()
        expect(val() == "" and shown() == ALL and pressed() == [], "pressing the pressed button clears the search")
        btn("Crypto").click()
        expect(shown() == ["c5"], "a button shows only the cards tagged with it, not cards whose text contains the word")
        type_("crypto")
        expect(shown() == ["c5"] and pressed() == ["Crypto"], "typing an industry exactly behaves like its button")
        type_("crypt")
        expect(shown() == ["c4", "c5"] and pressed() == [], "any other typing is a plain text search")
        type_("bank")
        expect(shown() == ["c1", "c2"], "a lone synonym finds its industry's cards only")
        expect(pressed() == ["Finance"], "a lone synonym lights its industry's button")
        type_("hospital")
        expect(shown() == ["c2"], "'hospital' finds Healthcare, not a card tagged Hospitality")
        type_("lawyer")
        expect(shown() == [], "a synonym does not match its industry's name in a card's prose ('legal staff')")
        type_("law")
        expect(shown() == [], "a synonym is matched as a whole word ('law' is not found in 'flaw')")
        type_("bank theta")
        expect(shown() == ["c8"], "beside other words, a synonym also matches itself as a whole word in the text")
        type_("finance")
        expect(pressed() == ["Finance"], "typing an industry presses its button")
        type_("industries")
        expect(shown() == [], "the skipped label inside a searched node is not searched")
        type_("slides")
        expect(shown() == [], "a searched node that is itself skipped is still left out")
        btn("Technology").click()
        key("Escape", "#q")
        expect(val() == "" and pressed() == [], "Escape clears the field and the pressed button")
        btn("Hospitality").click()
        key("Escape")
        expect(val() == "" and pressed() == [], "Escape with focus still on the pressed button clears the search")
        btn("Technology").click()
        pg.click(".card-finder-clear")
        pg.wait_for_timeout(150)
        expect(val() == "" and pressed() == [], "Clear the search clears the pressed button")
        browser.close()

    print(f"\njs test: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
