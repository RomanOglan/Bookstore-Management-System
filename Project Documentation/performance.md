# Performance evidence

Database: MySQL 8.0 running on my own computer, with about 1,000 books loaded from `bookstore.csv`.

How I got these results:

- EXPLAIN: I ran each statement in `performance_tests.sql` and pasted the plan under its heading.
- Load test: I ran `python load_test.py search` and `python load_test.py orders` and pasted the console output below.

## 1. Search (the SELECT inside SearchBooks)

```
-> Limit: 24 row(s)  (cost=808 rows=24)
    -> Nested loop left join  (cost=808 rows=1005)
        -> Filter: ((lower(b.Title) like <cache>((@pattern))) or (lower(coalesce(a.AuthorName,'')) like <cache>((@pattern))))  (cost=456 rows=1005)
            -> Nested loop left join  (cost=456 rows=1005)
                -> Sort: b.Title  (cost=104 rows=1005)
                    -> Table scan on b  (cost=104 rows=1005)
                -> Single-row index lookup on a using PRIMARY (AuthorID = b.AuthorID)  (cost=0.25 rows=1)
        -> Single-row index lookup on c using PRIMARY (CategoryID = b.CategoryID)  (cost=0.25 rows=1)
```

**What it shows:** MySQL reads the whole `Books` table (a table scan, 1,005 rows) and sorts it by title. It can't use the title index because the search pattern starts with `%`, and the `LOWER()` around the column would block the index anyway. With only about 1,000 books this is still quick. If the catalog got a lot bigger, a FULLTEXT index would be the fix. `Author` and `Category` are looked up by primary key, so they barely cost anything.

### 1b. EXPLAIN ANALYZE of the same search

```
-> Limit: 24 row(s)  (cost=456 rows=24) (actual time=3.24..3.38 rows=24 loops=1)
    -> Filter: ((lower(b.Title) like <cache>((@pattern))) or (lower(coalesce(a.AuthorName,'')) like <cache>((@pattern))))  (cost=456 rows=1005) (actual time=3.24..3.37 rows=24 loops=1)
        -> Nested loop left join  (cost=456 rows=1005) (actual time=2.45..2.51 rows=69 loops=1)
            -> Sort: b.Title  (cost=104 rows=1005) (actual time=2.43..2.44 rows=69 loops=1)
                -> Table scan on b  (cost=104 rows=1005) (actual time=0.204..0.98 rows=1005 loops=1)
            -> Single-row index lookup on a using PRIMARY (AuthorID = b.AuthorID)  (cost=0.25 rows=1) (actual time=902e-6..902e-6 rows=0.0145 loops=69)
```

**What it shows:** the real time. The whole search took about 3.4 ms, and most of that was the table scan and the sort.

## 2. PlaceOrder stock check (`SELECT ... FOR UPDATE`)

```
-> Rows fetched before execution  (cost=0..0 rows=1)
```

**What it shows:** the book is found with a primary key lookup (one row, worked out before the query even runs). So PlaceOrder only locks the one book being bought, and orders for different books don't have to wait on each other.

## 3. Order history (/orders)

```
-> Sort: o.OrderDate DESC, o.OrderID DESC
    -> Table scan on <temporary>
        -> Aggregate using temporary table
            -> Nested loop inner join  (cost=5.68 rows=11.6)
                -> Index lookup on o using UserID (UserID = (@customer_id))  (cost=1.6 rows=11)
                -> Index lookup on oi using OrderID (OrderID = o.OrderID)  (cost=0.274 rows=1.06)
```

**What it shows:** `Orders` is found with the `UserID` index (MySQL makes this one automatically for the foreign key), so only that customer's orders get read. `Order_Items` is then joined using its `OrderID` index. No table scans.

## 4. Order detail (/orders/<id>)

```
-> Sort: b.Title
    -> Stream results  (cost=0.7 rows=1)
        -> Nested loop inner join  (cost=0.7 rows=1)
            -> Index lookup on oi using OrderID (OrderID = (@order_id))  (cost=0.35 rows=1)
            -> Single-row index lookup on b using PRIMARY (BookID = oi.BookID)  (cost=0.35 rows=1)
```

**What it shows:** `Order_Items` is found by `OrderID` using its index and `Books` by primary key, so only the rows for that one order are touched.

## 5. Overdue loans

```
-> Nested loop inner join  (cost=3.86 rows=4)
    -> Nested loop inner join  (cost=3.26 rows=4)
        -> Nested loop inner join  (cost=2.66 rows=4)
            -> Sort: DaysOverdue DESC  (cost=2.06 rows=4)
                -> Index range scan on l using idx_loans_due over (DueDate < '2026-11-19'), with index condition: ((l.ReturnedDate is null) and (l.DueDate < <cache>(curdate())))  (cost=2.06 rows=4)
            -> Single-row index lookup on u using PRIMARY (UserID = l.UserID)  (cost=0.375 rows=1)
        -> Single-row index lookup on bc using PRIMARY (CopyID = l.CopyID)  (cost=0.375 rows=1)
    -> Single-row index lookup on b using PRIMARY (BookID = bc.BookID)  (cost=0.375 rows=1)
```

**What it shows:** it uses the `idx_loans_due` index as a range scan on `DueDate`, so only the overdue loans are read instead of the whole table (4 rows here). The other tables are joined by primary key. If there were very few loans overall, MySQL might pick a full scan instead because it's cheaper.

## 6. Load test: 50 simultaneous requests

Target: 95th percentile under 500 ms, with no errors.

### Search (`python load_test.py search`)

```
SearchBooks: 50 simultaneous requests
  succeeded: 50   rejected by the procedure: 0   errors: 0
  median: 114.3 ms   95th percentile: 135.5 ms   slowest: 138.0 ms
  total time for all 50: 503.2 ms
  target: 95th percentile under 500 ms with no errors -> PASS
```

**What it shows:** 50 searches at once all worked with no errors, and the slowest took 138 ms, well under the 500 ms target. So the table scan from section 1 is fine at this size.

### Orders (`python load_test.py orders`)

```
Book 101 (1984), starting stock 8, buyer customer@bookstore.local

PlaceOrder: 50 simultaneous requests
  succeeded: 8   rejected by the procedure: 42   errors: 0
  median: 88.5 ms   95th percentile: 90.1 ms   slowest: 90.5 ms
  total time for all 50: 165.8 ms
  target: 95th percentile under 500 ms with no errors -> PASS

  stock before: 8   stock after: 0
  successful orders: 8, expected 8 -> PASS
  stock never below zero and before - sold == after -> PASS
  restocked with RestockBook: quantity is back to 8
```

**What it shows:** 50 customers try to buy the same book at the same time. The number of orders that succeed matches the stock we started with (8), and everyone else gets the "insufficient stock" error from the procedure. Stock ends at 0 and never goes negative. This works because `SELECT ... FOR UPDATE` in PlaceOrder makes the orders line up for the row lock, so the book can't be oversold. At the end the script restocks the book with RestockBook.
