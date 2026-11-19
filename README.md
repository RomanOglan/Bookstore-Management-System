# Bookstore / Library Database (COMP-4150)

A website where customers can buy and borrow books and staff can manage the books, orders and loans. Built with Flask and MySQL 8.

## How to run it

You need Python 3, Git and MySQL 8 installed, and MySQL has to be running.

1. Clone the repo and go into the folder.
2. Make a virtual environment and install the packages.
   - Mac: `python3 -m venv venv`, then `source venv/bin/activate`
   - Windows: `py -m venv venv`, then `.\venv\Scripts\Activate.ps1`
   - Then: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and put in your own MySQL user and password. Don't commit `.env`.
4. Set up the database: `python3 setup_database.py`
5. Run the tests: `python3 -m unittest -v`
6. Start the app: `python3 app.py` and open http://127.0.0.1:5001

Everyone has their own local database, so after every `git pull` run `python3 setup_database.py` again. It's safe to re-run because it doesn't delete any data. It builds the tables, loads about 1,000 books from `bookstore.csv`, adds demo stock and demo copies for borrowing, installs the stored procedures and triggers, and creates the demo logins. (Only use `--reset` if you really want to wipe your database.)

Demo logins:
- Customer: `customer@bookstore.local` / `Customer123!`
- Staff: `staff@bookstore.local` / `Staff123!`

## What it does

**Customers** can search the catalog (by title, author or ISBN, with a category filter), buy books, borrow books for 14 days, return them, see their orders and loans, and see any late fees. New customers can register on the site.

**Staff** can add, edit and delete books, restock, add lendable copies, see a low stock list, see all orders (with filters), and see and return loans (overdue ones are highlighted).

Late fees are $0.25 per day. A patron can have at most 5 loans at once and can't borrow if they have an overdue book.

## How it works

- `app.py` is the Flask app. Customer and Staff access is checked in the code.
- `bookstore.sql` has the tables, and `setup_database.py` runs everything.
- Most of the work is done in stored procedures (`stored_procedures.sql`) that the app calls: `SearchBooks`, `PlaceOrder`, `BorrowBook`, `ReturnBook`, `MarkOverdueLoans`, `AddBook`, `UpdateBook`, `DeleteBook`, `RestockBook`, `AddBookCopy` and `LowStockReport`. They check the input and use transactions, so a failed step undoes everything. The app shows their error messages to the user.
- Triggers (`triggers.sql`): `ValidateOrderItem` (no bad quantities or prices), `ValidateLoanDates` (due date can't be before the borrow date), `BlockLoanReopen` (a returned loan can't be reopened) and `FreeCopyOnReturn` (the copy becomes available when a loan is returned).
- `backend_queries.sql` has the reporting queries: overdue loans, low stock, sales by category, top sellers and a customer's order history.
- `performance_tests.sql`, `load_test.py` and `Project Documentation/performance.md` have the EXPLAIN results and load tests.
- `roles.sql` sets up database roles for customers and staff. The app itself connects as one MySQL user and checks roles in the code, so these roles are just the design we documented. Run it as root after `setup_database.py`.
- `test_data.sql` is optional extra sample data and isn't loaded by the setup script.

## Team

- Mona Hicham Moussa
- Roman Oglan
- Taha Hammoud
- Stefan Bratic
