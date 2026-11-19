
import argparse
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from mysql.connector import Error

import mysql.connector

from db import connection_settings


def get_connection():
    # Pure-Python driver: the C extension can crash (segmentation fault) with 50 threads.
    return mysql.connector.connect(**connection_settings(), use_pure=True)

THREADS = 50
TARGET_MS = 500
CUSTOMER_EMAIL = "customer@bookstore.local"
SEARCH_TERMS = ["the", "love", "history", "night", "girl", "world", "life", "house", "secret", "war"]


def call(conn, name, args):
    cur = conn.cursor()
    try:
        cur.callproc(name, args)
        results = [r.fetchall() for r in cur.stored_results()]
        conn.commit()
        return results
    finally:
        cur.close()


def scalar(sql, params=()):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
    finally:
        conn.close()


def percentile(values, pct):
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100
    low = int(k)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (k - low)


def run_threads(job):
    barrier = threading.Barrier(THREADS)

    def worker(i):
        try:
            conn = get_connection()
        except Exception:
            barrier.abort()  # let the other threads stop instead of waiting
            raise
        try:
            barrier.wait(timeout=60)
            start = time.perf_counter()
            try:
                detail = job(i, conn)
                status = "ok"
            except Error as exc:
                if exc.errno != 1644:
                    status, detail = "error", f"{exc.errno}: {exc.msg}"
                else:
                    status, detail = "rejected", exc.msg
            return status, (time.perf_counter() - start) * 1000, detail
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        return list(pool.map(worker, range(THREADS)))


def report(title, results, wall_ms):
    times = [ms for _, ms, _ in results]
    median = statistics.median(times)
    p95 = percentile(times, 95)
    slowest = max(times)
    counts = {s: sum(1 for status, _, _ in results if status == s) for s in ("ok", "rejected", "error")}
    print(f"\n{title}: {THREADS} simultaneous requests")
    print(f"  succeeded: {counts['ok']}   rejected by the procedure: {counts['rejected']}   errors: {counts['error']}")
    print(f"  median: {median:.1f} ms   95th percentile: {p95:.1f} ms   slowest: {slowest:.1f} ms")
    print(f"  total time for all {THREADS}: {wall_ms:.1f} ms")
    verdict = "PASS" if p95 <= TARGET_MS and counts["error"] == 0 else "FAIL"
    print(f"  target: 95th percentile under {TARGET_MS} ms with no errors -> {verdict}")
    for status, _, detail in results:
        if status == "error":
            print("  error:", detail)
    return counts, verdict


def search_test():
    def job(i, conn):
        term = SEARCH_TERMS[i % len(SEARCH_TERMS)]
        results = call(conn, "SearchBooks", (term, None, 24, 0))
        return f"{term}: {results[0][0][0]} matches"

    start = time.perf_counter()
    results = run_threads(job)
    _, verdict = report("SearchBooks", results, (time.perf_counter() - start) * 1000)
    return verdict == "PASS"


def orders_test(book_id):
    user_id = scalar("SELECT UserID FROM Users WHERE Email=%s AND AccountStatus='Active'", (CUSTOMER_EMAIL,))
    if user_id is None:
        raise SystemExit(f"No active user {CUSTOMER_EMAIL}. Run python setup_database.py first.")
    if book_id is None:
        book_id = scalar("SELECT MIN(BookID) FROM Books WHERE Quantity > 0")
        if book_id is None:
            raise SystemExit("No book has stock. Restock one on the Manage books page, or pass --book-id.")
    start_stock = scalar("SELECT Quantity FROM Books WHERE BookID=%s", (book_id,))
    if not start_stock:
        raise SystemExit(f"Book {book_id} has no stock. Restock it first.")
    title = scalar("SELECT Title FROM Books WHERE BookID=%s", (book_id,))
    print(f"Book {book_id} ({title}), starting stock {start_stock}, buyer {CUSTOMER_EMAIL}")

    def job(i, conn):
        results = call(conn, "PlaceOrder", (user_id, book_id, 1, "Pick-Up"))
        return f"order {results[0][0][0]}"

    start = time.perf_counter()
    results = run_threads(job)
    counts, verdict = report("PlaceOrder", results, (time.perf_counter() - start) * 1000)

    end_stock = scalar("SELECT Quantity FROM Books WHERE BookID=%s", (book_id,))
    expected = min(start_stock, THREADS)
    sold = counts["ok"]
    print(f"\n  stock before: {start_stock}   stock after: {end_stock}")
    print(f"  successful orders: {sold}, expected {expected} -> {'PASS' if sold == expected else 'FAIL'}")
    print(f"  stock never below zero and before - sold == after -> "
          f"{'PASS' if end_stock is not None and end_stock >= 0 and end_stock == start_stock - sold else 'FAIL'}")

    if sold:
        conn = get_connection()
        try:
            restocked = call(conn, "RestockBook", (book_id, sold))[0][0][1]
        finally:
            conn.close()
        print(f"  restocked with RestockBook: quantity is back to {restocked}")
    return verdict == "PASS" and sold == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["search", "orders"])
    parser.add_argument("--book-id", type=int, help="book to order in orders mode (default: first book with stock)")
    args = parser.parse_args()
    passed = search_test() if args.mode == "search" else orders_test(args.book_id)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
