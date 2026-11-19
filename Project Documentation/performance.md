# Performance evidence

Database: MySQL 8.0 on a local machine, with about 1,000 books from `bookstore.csv`.

How it was produced:

- EXPLAIN output: run each statement in `performance_tests.sql` in MySQL Workbench and paste the result grid under its heading.
- Load test: `python load_test.py search` and `python load_test.py orders`, with the console output pasted below.

> Replace every `PASTE` block with your real output before submitting.

## 1. Search (the SELECT inside SearchBooks)

```
PASTE EXPLAIN OUTPUT
```

**What it shows:** `Books` is read with `type = ALL`, which is a full table scan. `LIKE '%word%'` starts with a wildcard, so the `idx_books_title` index can't be used. `LOWER(...)` around the column would also stop the index from being used. On about 1,000 rows this is still fast (see query 1b and the load test). At a much larger catalog, a FULLTEXT index would be the fix. `Author` and `Category` are joined by primary key (`eq_ref`), so they add almost nothing.

### 1b. EXPLAIN ANALYZE of the same search

```
PASTE EXPLAIN ANALYZE OUTPUT
```

**What it shows:** the real time for the scan, in milliseconds.

## 2. PlaceOrder stock check (`SELECT ... FOR UPDATE`)

```
PASTE EXPLAIN OUTPUT
```

**What it shows:** a primary-key lookup (`type = const`, 1 row). This means PlaceOrder locks only the one book being bought, so orders for different books don't block each other.

## 3. Order history (/orders)

```
PASTE EXPLAIN OUTPUT
```

**What it shows:** `Orders` is found through the index on `UserID` that MySQL creates for the `fk_orders_user` foreign key (`type = ref`), so only that customer's orders are read. `Order_Items` is joined through the `fk_items_order` index.

## 4. Order detail (/orders/<id>)

```
PASTE EXPLAIN OUTPUT
```

**What it shows:** `Order_Items` is found by `OrderID` through the `fk_items_order` index (`ref`), and `Books` by primary key (`eq_ref`). Only the rows for one order are touched.

## 5. Overdue loans

```
PASTE EXPLAIN OUTPUT
```

**What it shows:** `Loans` can use `idx_loans_due (DueDate, ReturnedDate)` as a range on `DueDate`. With very few loans, the optimizer may choose a full scan instead (`type = ALL`), because it's cheaper. The other tables are joined by primary key.

## 6. Load test: 50 simultaneous requests

Target: 95th percentile under 500 ms, with no errors.

### Search (`python load_test.py search`)

```
PASTE OUTPUT
```

### Orders (`python load_test.py orders`)

```
PASTE OUTPUT
```

**What it shows:** fifty customers try to buy the same book at once. Exactly as many orders succeed as there were copies in stock. The rest get the procedure's "insufficient stock" error, and the stock ends at 0, never below. `SELECT ... FOR UPDATE` inside PlaceOrder makes the orders queue for the row lock, so the book is never oversold. Afterwards the script puts the stock back with RestockBook.
