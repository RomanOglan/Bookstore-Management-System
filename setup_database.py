"""Create/update the local schema and idempotently import bookstore.csv."""

import argparse
import csv
from pathlib import Path

from werkzeug.security import generate_password_hash

from db import get_connection

ROOT = Path(__file__).resolve().parent
DB_NAME = "Bookstore"


def sql_statements(path):
    delimiter = ";"
    statement = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split(maxsplit=1)[1]
            continue
        if not stripped or stripped.startswith("--"):
            continue
        statement.append(line)
        if stripped.endswith(delimiter):
            sql = "\n".join(statement).rstrip()
            yield sql[:-len(delimiter)].rstrip()
            statement = []
    if statement:
        yield "\n".join(statement)


def create_schema(reset=False):
    server = get_connection(include_database=False)
    try:
        cur = server.cursor()
        if reset:
            cur.execute(f"DROP DATABASE IF EXISTS `{DB_NAME}`")
        for statement in sql_statements(ROOT / "bookstore.sql"):
            cur.execute(statement)
        cur.close()
    finally:
        server.close()


def install_database_logic(conn):
    cur = conn.cursor()
    try:
        for path in (ROOT / "stored_procedures.sql", ROOT / "triggers.sql"):
            for statement in sql_statements(path):
                cur.execute(statement)
    finally:
        cur.close()


def apply_safe_migrations(conn):
    """Bring earlier team schemas forward without deleting rows."""
    cur = conn.cursor()
    migrations = [
        "ALTER TABLE Users MODIFY Role VARCHAR(20) NOT NULL",
        "UPDATE Users SET Role='Customer' WHERE Role IN ('Users', 'User')",
        "UPDATE Users SET Role='Staff' WHERE Role='Admin'",
        "ALTER TABLE Users MODIFY Role ENUM('Customer','Staff') NOT NULL DEFAULT 'Customer'",
        "ALTER TABLE Users MODIFY AccountStatus VARCHAR(20) NOT NULL",
        "UPDATE Users SET AccountStatus='Inactive' WHERE AccountStatus='Unactive'",
        "ALTER TABLE Users MODIFY AccountStatus ENUM('Active','Inactive') NOT NULL DEFAULT 'Active'",
        "ALTER TABLE Category MODIFY CategoryName VARCHAR(100) NOT NULL",
        "ALTER TABLE Books MODIFY ISBN VARCHAR(13) NULL",
        "ALTER TABLE Books MODIFY Title VARCHAR(255) NOT NULL",
        "ALTER TABLE Books MODIFY Description VARCHAR(1000) NULL",
        "ALTER TABLE Books MODIFY Price DECIMAL(10,2) NOT NULL",
        "ALTER TABLE Books MODIFY Quantity SMALLINT UNSIGNED NULL",
        "ALTER TABLE Books ADD COLUMN CatalogStatus VARCHAR(50) NULL",
        "ALTER TABLE Books ADD COLUMN SourceURL VARCHAR(500) NULL UNIQUE",
        "ALTER TABLE Book_Copies MODIFY Barcode VARCHAR(50) NOT NULL",
        "ALTER TABLE Orders MODIFY OrderDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE Order_Items MODIFY Quantity SMALLINT UNSIGNED NOT NULL",
        "ALTER TABLE Order_Items MODIFY Price DECIMAL(10,2) NOT NULL",
        "ALTER TABLE Loans ADD COLUMN LateFee DECIMAL(8,2) NOT NULL DEFAULT 0",
    ]
    for statement in migrations:
        try:
            cur.execute(statement)
        except Exception as exc:
            if getattr(exc, "errno", None) not in {1060, 1061, 1091}:
                raise
    conn.commit()
    cur.close()


def import_catalog(conn):
    rows = list(csv.DictReader((ROOT / "bookstore.csv").open(encoding="utf-8-sig", newline="")))
    required = {"title", "price", "stock", "rating", "category", "book_url"}
    if not rows or set(rows[0]) != required:
        raise ValueError("bookstore.csv is empty or does not have the six expected source columns")
    source_urls = [row["book_url"].strip() for row in rows]
    if len(source_urls) != len(set(source_urls)):
        raise ValueError("bookstore.csv contains duplicate source URLs; import stopped to prevent duplicate records")

    cur = conn.cursor()
    categories = sorted({row["category"].strip() for row in rows})
    cur.executemany(
        "INSERT INTO Category (CategoryName) VALUES (%s) ON DUPLICATE KEY UPDATE CategoryName=VALUES(CategoryName)",
        [(name,) for name in categories],
    )
    cur.execute("SELECT CategoryID, CategoryName FROM Category")
    category_ids = {name: category_id for category_id, name in cur.fetchall()}

    values = []
    for row in rows:
        price = float(row["price"])
        rating = int(row["rating"])
        if price < 0 or not 1 <= rating <= 5 or not row["title"].strip() or not row["book_url"].strip():
            raise ValueError(f"Invalid catalog row: {row!r}")
        values.append((
            row["title"].strip(), price, rating, row["stock"].strip(),
            row["book_url"].strip(), category_ids[row["category"].strip()],
        ))
    cur.executemany(
        """INSERT INTO Books (Title, Price, Rating, Quantity, CatalogStatus, SourceURL, CategoryID)
           VALUES (%s, %s, %s, NULL, %s, %s, %s)
           ON DUPLICATE KEY UPDATE Title=VALUES(Title), Price=VALUES(Price),
             Rating=VALUES(Rating), CatalogStatus=VALUES(CatalogStatus),
             CategoryID=VALUES(CategoryID)""",
        values,
    )
    conn.commit()
    cur.execute("SELECT SourceURL FROM Books WHERE SourceURL IS NOT NULL")
    saved_urls = {url for (url,) in cur.fetchall()}
    cur.close()
    missing = set(source_urls) - saved_urls
    if missing:
        raise RuntimeError(f"Catalog verification failed: {len(missing)} source rows are missing")
    return len(rows)


def apply_demo_stock(conn):
    """Give catalog books that have no quantity a demo stock level (3-17 copies).
    Only touches rows where Quantity IS NULL, so staff edits are never overwritten.
    The CSV has no stock numbers, so these are made-up test values."""
    cur = conn.cursor()
    cur.execute("UPDATE Books SET Quantity = 3 + (BookID % 15) WHERE Quantity IS NULL")
    updated = cur.rowcount
    conn.commit()
    cur.close()
    return updated


def ensure_demo_users(conn):
    """Create local demo logins only when those emails do not already exist."""
    cur = conn.cursor()
    users = [
        ("Demo Customer", "customer@bookstore.local", "Customer", "Customer123!"),
        ("Demo Staff", "staff@bookstore.local", "Staff", "Staff123!"),
    ]
    for name, email, role, password in users:
        cur.execute(
            """INSERT INTO Users (Name, Email, PasswordHash, Role, AccountStatus)
               VALUES (%s, %s, %s, %s, 'Active')
               ON DUPLICATE KEY UPDATE Name=VALUES(Name), Role=VALUES(Role)""",
            (name, email, generate_password_hash(password), role),
        )
    conn.commit()
    cur.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="delete and rebuild the local Bookstore database")
    parser.add_argument("--confirm-reset", help="must be exactly Bookstore when --reset is used")
    args = parser.parse_args()
    if args.reset and args.confirm_reset != DB_NAME:
        parser.error("--reset requires --confirm-reset Bookstore")

    create_schema(reset=args.reset)
    conn = get_connection()
    try:
        apply_safe_migrations(conn)
        imported = import_catalog(conn)
        stocked = apply_demo_stock(conn)
        ensure_demo_users(conn)
        install_database_logic(conn)
    finally:
        conn.close()
    print(f"Database ready. Verified CSV catalog rows: {imported}.")
    print(f"Demo stock added to {stocked} books that had no quantity.")
    print("Existing orders, loans, quantities, and non-CSV books were preserved." if not args.reset else "Bookstore was intentionally rebuilt.")


if __name__ == "__main__":
    main()
