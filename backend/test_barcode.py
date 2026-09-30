"""Tests for barcode handling."""

import sqlite3
import sys

from app.barcode import (
    InvalidBarcode,
    LookupUnavailable,
    Product,
    barcode_report,
    compose_name,
    gtin_check_digit,
    normalize_barcode,
    remember_barcode,
    resolve_barcode,
)
from app.db import SCHEMA
from app.taxonomy import seed

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}\n          got:  {got}\n          want: {want}")
        failures.append(label)


def raises(fn, exc_type):
    try:
        fn()
    except exc_type as err:
        return str(err)
    return None


def fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    seed(conn)
    return conn


class FakeSource:
    """A lookup source that answers from a script and counts its calls."""

    def __init__(self, answer):
        self.answer = answer   # a Product, None, or an Exception to raise
        self.calls = 0

    def __call__(self, barcode):
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def sources(*fakes):
    return [(f"Source{i}", fake) for i, fake in enumerate(fakes, start=1)]


print("\ncheck digits -- the textbook examples")
check("UPC-A 03600029145_ -> 2", gtin_check_digit("03600029145"), 2)
check("EAN-13 400638133393_ -> 1", gtin_check_digit("400638133393"), 1)

print("\nnormalize_barcode")
check("a 12-digit UPC-A is widened to EAN-13",
      normalize_barcode("036000291452"), "0036000291452")
check("the same code as EAN-13 is left alone",
      normalize_barcode("0036000291452"), "0036000291452")
check("...so both spellings meet in the cache",
      normalize_barcode("036000291452") == normalize_barcode("0036000291452"), True)
check("printed grouping (spaces) is removed",
      normalize_barcode(" 0 36000 29145 2 "), "0036000291452")
check("dashes too", normalize_barcode("4-006381-333931"), "4006381333931")
check("a leading-zero GTIN-14 narrows to EAN-13",
      normalize_barcode("00036000291452"), "0036000291452")
check("EAN-8 is kept as-is", normalize_barcode("96385074"), "96385074")

check("a mistyped digit is caught by the check digit",
      raises(lambda: normalize_barcode("036000291453"), InvalidBarcode),
      "That barcode's check digit doesn't add up; probably a typo.")
check("letters are rejected",
      raises(lambda: normalize_barcode("03600029145X"), InvalidBarcode),
      "A barcode is digits only.")
check("wrong lengths are rejected, saying how long it was",
      raises(lambda: normalize_barcode("12345"), InvalidBarcode),
      "Barcodes are 8, 12, 13 or 14 digits long; that one is 5.")
check("empty input is rejected",
      raises(lambda: normalize_barcode("  "), InvalidBarcode), "Enter a barcode.")

print("\ncompose_name")
check("brand + name when the name lacks the brand",
      compose_name("Carpano", "Antica Formula"), "Carpano Antica Formula")
check("name alone when it already says the brand",
      compose_name("Campari", "Campari Bitter"), "Campari Bitter")
check("...case-insensitively", compose_name("CAMPARI", "Campari Bitter"), "Campari Bitter")
check("brand alone when there's no name", compose_name("Aperol", ""), "Aperol")
check("name alone when there's no brand", compose_name(None, "Dry Vermouth"), "Dry Vermouth")


print("\nthe lookup chain")
CODE = "0036000291452"

db = fresh_db()
first = FakeSource(Product("Campari", "Campari", "openfoodfacts"))
second = FakeSource(Product("never used", None, "upcitemdb"))
result = resolve_barcode(db, CODE, sources(first, second))
check("the first source's answer is used", result["product_name"], "Campari")
check("...and the second source is never asked", second.calls, 0)
check("...and it went to the network", result["cached"], False)

again = resolve_barcode(db, CODE, sources(first, second))
check("asking twice doesn't ask twice -- it's cached", first.calls, 1)
check("...and the cached answer says so", again["cached"], True)
check("...and matches", again["product_name"], "Campari")

db = fresh_db()
first = FakeSource(None)
second = FakeSource(Product("Dolin Dry Vermouth", "Dolin", "upcitemdb"))
result = resolve_barcode(db, CODE, sources(first, second))
check("a miss falls through to the next source", result["product_name"], "Dolin Dry Vermouth")
check("...and records which source knew", result["source"], "upcitemdb")

db = fresh_db()
first, second = FakeSource(None), FakeSource(None)
result = resolve_barcode(db, CODE, sources(first, second))
check("nobody knows: found nothing, no error", (result["product_name"], result["lookup_error"]), (None, None))
resolve_barcode(db, CODE, sources(first, second))
check("...and that clean miss is cached -- no second round of asking",
      (first.calls, second.calls), (1, 1))

print("\nerrors are never cached -- the important one")
db = fresh_db()
down = FakeSource(LookupUnavailable("timed out"))
also_down = FakeSource(LookupUnavailable("HTTP 503"))
result = resolve_barcode(db, CODE, sources(down, also_down))
check("both unreachable: says which, in words",
      result["lookup_error"], "Couldn't reach Source1 or Source2 right now.")
resolve_barcode(db, CODE, sources(down, also_down))
check("...and asks again next time instead of remembering 'unknown'",
      (down.calls, also_down.calls), (2, 2))

db = fresh_db()
down = FakeSource(LookupUnavailable("timed out"))
nope = FakeSource(None)
resolve_barcode(db, CODE, sources(down, nope))
resolve_barcode(db, CODE, sources(down, nope))
check("one unreachable + one 'not found' is NOT cached as a miss either",
      down.calls, 2)

db = fresh_db()
down = FakeSource(LookupUnavailable("timed out"))
found = FakeSource(Product("Aperol", "Aperol", "upcitemdb"))
result = resolve_barcode(db, CODE, sources(down, found))
check("one source down, the next one answers: no error shown",
      (result["product_name"], result["lookup_error"]), ("Aperol", None))

print("\nold misses are retried")
db = fresh_db()
with db:
    db.execute(
        "INSERT INTO barcode_product (barcode, source, looked_up_at) "
        "VALUES (?, 'none', datetime('now', '-45 days'))",
        (CODE,),
    )
late = FakeSource(Product("Luxardo Maraschino", "Luxardo", "openfoodfacts"))
result = resolve_barcode(db, CODE, sources(late))
check("a 45-day-old 'nobody knows' gets asked again", late.calls, 1)
check("...and the database has since learned it", result["product_name"], "Luxardo Maraschino")

db = fresh_db()
with db:
    db.execute("INSERT INTO barcode_product (barcode, source) VALUES (?, 'none')", (CODE,))
fresh = FakeSource(Product("x", None, "upcitemdb"))
resolve_barcode(db, CODE, sources(fresh))
check("a fresh miss is not", fresh.calls, 0)


print("\nremembering what you confirmed")
db = fresh_db()
resolve_barcode(db, CODE, sources(FakeSource(Product("CAMPARI BITTER 750ML", "Campari", "upcitemdb"))))
with db:
    remember_barcode(db, CODE, "Campari", "campari")
row = db.execute("SELECT * FROM barcode_product WHERE barcode = ?", (CODE,)).fetchone()
check("your tidied name replaces the database's", row["product_name"], "Campari")
check("the category you picked is stored against the barcode", row["ingredient_id"], "campari")
check("...and the original source is kept", row["source"], "upcitemdb")

db = fresh_db()
resolve_barcode(db, CODE, sources(FakeSource(None)))
with db:
    remember_barcode(db, CODE, "House Bitters", "aromatic-bitters")
check("a barcode nobody knew becomes 'manual' once you name it",
      db.execute("SELECT source FROM barcode_product WHERE barcode=?", (CODE,)).fetchone()["source"],
      "manual")

db = fresh_db()
with db:
    remember_barcode(db, CODE, "Brand New Thing", "vodka")
check("remembering a barcode that was never looked up works too",
      db.execute("SELECT product_name FROM barcode_product WHERE barcode=?", (CODE,)).fetchone()["product_name"],
      "Brand New Thing")


print("\nbarcode_report -- what the UI gets")
db = fresh_db()
report = barcode_report(db, CODE, sources(FakeSource(Product("Carpano Antica Formula", "Carpano", "openfoodfacts"))))
check("found online, never confirmed: the alias map suggests a category",
      (report["found"], report["ingredient_id"], report["suggested_ingredient_id"]),
      (True, None, "sweet-vermouth"))
check("...with its display name", report["suggested_ingredient_name"], "Sweet Vermouth")
check("...and nothing on the shelf yet", report["on_shelf"], [])

with db:
    db.execute(
        "INSERT INTO bottle (product_name, ingredient_id, barcode) VALUES (?, ?, ?)",
        ("Carpano Antica Formula", "sweet-vermouth", CODE),
    )
    remember_barcode(db, CODE, "Carpano Antica Formula", "sweet-vermouth")
never = FakeSource(Product("should not be asked", None, "upcitemdb"))
report = barcode_report(db, CODE, sources(never))
check("a rescan knows it's on the shelf",
      [b["product_name"] for b in report["on_shelf"]], ["Carpano Antica Formula"])
check("...knows the category you confirmed (no guessing needed)",
      (report["ingredient_id"], report["ingredient_name"], report["suggested_ingredient_id"]),
      ("sweet-vermouth", "Sweet Vermouth", None))
check("...and never touched the network", never.calls, 0)

with db:
    db.execute("DELETE FROM bottle")
report = barcode_report(db, CODE, sources(never))
check("finish the bottle, buy another: the barcode is still remembered",
      (report["on_shelf"], report["ingredient_id"], report["product_name"]),
      ([], "sweet-vermouth", "Carpano Antica Formula"))

db = fresh_db()
report = barcode_report(db, CODE, sources(FakeSource(None)))
check("unknown everywhere: found=False, no suggestion, no error",
      (report["found"], report["suggested_ingredient_id"], report["lookup_error"]),
      (False, None, None))

print("\nparsing each source's documented response shapes")
import app.barcode as bc
from app.barcode import _get_json, open_food_facts, upcitemdb


def with_response(status, body, fn):
    """Run a source function with _get_json replaced by a canned answer."""
    original = bc._get_json
    bc._get_json = lambda url: (status, body)
    try:
        return fn(CODE)
    finally:
        bc._get_json = original


off_found = {"status": 1, "product": {"product_name": "Antica Formula", "brands": "Carpano, Branca"}}
check("OFF found: first brand + name composed",
      with_response(200, off_found, open_food_facts),
      Product("Carpano Antica Formula", "Carpano", "openfoodfacts"))
check("OFF prefers the English name when there is one",
      with_response(200, {"status": 1, "product": {"product_name": "Amer", "product_name_en": "Bitter", "brands": "Campari"}}, open_food_facts).name,
      "Campari Bitter")
check("OFF 'status 0' means not found",
      with_response(200, {"status": 0, "status_verbose": "product not found"}, open_food_facts), None)
check("OFF 404 means not found", with_response(404, {"status": 0}, open_food_facts), None)
check("OFF found but nameless and brandless is treated as not found",
      with_response(200, {"status": 1, "product": {}}, open_food_facts), None)
check("OFF 429 (rate limited) is 'unreachable', not 'unknown'",
      raises(lambda: with_response(429, None, open_food_facts), LookupUnavailable),
      "Open Food Facts answered HTTP 429")
check("OFF 500 is unreachable too",
      raises(lambda: with_response(500, None, open_food_facts), LookupUnavailable) is not None, True)

upc_found = {"code": "OK", "total": 1, "items": [{"title": "Dolin Dry Vermouth de Chambery 750ml", "brand": "Dolin"}]}
check("UPCitemdb found: title kept whole when it already has the brand",
      with_response(200, upc_found, upcitemdb),
      Product("Dolin Dry Vermouth de Chambery 750ml", "Dolin", "upcitemdb"))
check("UPCitemdb empty items means not found",
      with_response(200, {"code": "OK", "total": 0, "items": []}, upcitemdb), None)
check("UPCitemdb 400 INVALID_UPC means not found",
      with_response(400, {"code": "INVALID_UPC"}, upcitemdb), None)
check("UPCitemdb 429 TOO_FAST is unreachable",
      raises(lambda: with_response(429, {"code": "TOO_FAST"}, upcitemdb), LookupUnavailable),
      "UPCitemdb answered HTTP 429")


print("\n_get_json against a real local HTTP server")
import http.server, json as _json, threading, time


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.seen_user_agent = self.headers.get("User-Agent")
        routes = {
            "/ok": (200, _json.dumps({"hello": "world"})),
            "/missing": (404, _json.dumps({"status": 0})),
            "/slow-down": (429, "rate limited"),
            "/broken": (500, "<html>oops</html>"),
            "/not-json": (200, "<html>definitely not json</html>"),
        }
        if self.path == "/hang":
            time.sleep(2)
            status, body = 200, "{}"
        else:
            status, body = routes[self.path]
        try:
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body.encode())
        except (BrokenPipeError, ConnectionResetError):
            # The /hang test expects the client to time out.
            pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_address[1]}"

check("200 JSON comes back parsed", _get_json(base + "/ok"), (200, {"hello": "world"}))
check("...sending our User-Agent, as Open Food Facts asks",
      server.seen_user_agent, bc.USER_AGENT)
check("404 is an answer, not a failure", _get_json(base + "/missing"), (404, {"status": 0}))
check("429 with a non-JSON body still returns its status", _get_json(base + "/slow-down"), (429, None))
check("500 returns its status for the caller to judge", _get_json(base + "/broken"), (500, None))
check("200 that isn't JSON is 'unreachable' -- the answer is unusable",
      raises(lambda: _get_json(base + "/not-json"), LookupUnavailable) is not None, True)

saved_timeout = bc.TIMEOUT_SECONDS
bc.TIMEOUT_SECONDS = 0.5
started = time.monotonic()
hung = raises(lambda: _get_json(base + "/hang"), LookupUnavailable)
elapsed = time.monotonic() - started
bc.TIMEOUT_SECONDS = saved_timeout
check("a server that hangs is cut off at the timeout", hung is not None and elapsed < 1.5, True)

server.shutdown()
dead_port = server.server_address[1]
check("a server that isn't there at all is 'unreachable'",
      raises(lambda: _get_json(f"http://127.0.0.1:{dead_port}/ok"), LookupUnavailable) is not None, True)

print()
if failures:
    print(f"{len(failures)} failed: {', '.join(failures)}")
    sys.exit(1)
print("all good")
