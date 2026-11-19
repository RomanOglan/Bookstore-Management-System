# Bookstore Management System

COMP-4150 Online Bookstore/Library Management System using the team's existing Flask, MySQL 8.0, HTML/CSS, and Python tooling.

## What was verified

`bookstore.csv` is the repository's complete online-source catalog. It currently contains **1,000 data rows** (not a target or assumption): every row has a title, price, stock text, 1-5 rating, category, and unique source URL. The importer always reads the complete file, so it will also work if the team later replaces it with a larger verified file.

The source file does **not** contain ISBNs, authors, descriptions, or numeric quantities. Those fields remain `NULL`/"not set" until staff provide them. The text `In stock` is retained as `CatalogStatus`; it is not converted into a made-up quantity. Both records named *The Star-Touched Queen* are retained because they have different source URLs.

The old five-book `test_data.sql` is sample SQL, separate from the verified online catalog. It remains in the repository for database-class demonstrations but is not loaded by the normal setup command.

## Features

- Paginated catalog from MySQL; case-insensitive title, author, and ISBN search; category filter and detail pages
- Customer and Staff login roles, inactive-account checks, CSRF form protection, parameterized SQL, and server-side validation
- Atomic purchasing: locks stock, creates the order and line item, and reduces inventory in one transaction
- Atomic borrowing/returning: a specific copy changes state together with its loan; five-active-loan limit
- Customer order and loan history
- Staff-only create, read, update, and delete, protected deletion of referenced books, and lendable barcode creation
- Idempotent catalog import and an explicit, guarded database reset

## DATA SAFETY AND LOCAL DATABASES

`python setup_database.py` is the normal safe command. It creates missing objects, upgrades the earlier team schema, imports/updates every CSV row by its unique source URL, and preserves existing books, quantities, orders, loans, and copies.

Only this explicit command deletes the local `Bookstore` database:

```powershell
python setup_database.py --reset --confirm-reset Bookstore
```

Use reset only after making a MySQL backup and only when a clean rebuild is intentional. A Git pull updates files; it does **not** copy anyone's live MySQL changes. Each group member owns a separate local database. To share database content, commit an approved seed/migration file that contains no private information, then have each member run it locally.

## PROJECT OWNER SETUP AND VERIFICATION (TAHA)

1. Open PowerShell and enter the project folder:

   ```powershell
   cd "C:\path\to\Bookstore-Management-System"
   code .
   ```

2. Create a virtual environment and install the existing requirements:

   ```powershell
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

   If PowerShell blocks activation, run this once in the same window, then activate again:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

3. Create local configuration:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Set `DB_USER`, `DB_PASSWORD`, and (if needed) `DB_HOST`/`DB_PORT` for your local MySQL 8.0 server. Keep `DB_NAME=Bookstore`. Do not commit `.env`.

4. If your current five-book database matters, back it up before the first migration:

   ```powershell
   mysqldump -u root -p --databases Bookstore --routines --triggers > bookstore-before-migration.sql
   ```

5. Run the safe setup/import (do not use `--reset`):

   ```powershell
   python setup_database.py
   ```

   It should report the number of rows actually read from `bookstore.csv`. Existing transactions remain untouched.

6. Run automated checks and start Flask:

   ```powershell
   python -m unittest -v
   python app.py
   ```

7. Visit <http://127.0.0.1:5001/dbtest>. It should show **1,000 verified CSV rows**. The total can be higher if your preserved local database already had additional books. Then test the catalog, search, login, CRUD, a purchase, a borrow, and a return.

8. Local demo accounts created by setup:

   - Customer: `customer@bookstore.local` / `Customer123!`
   - Staff: `staff@bookstore.local` / `Staff123!`

   These are local class-project accounts. Change or remove them before any public deployment.

9. Before sharing changes:

   ```powershell
   git status
   git diff
   git add app.py db.py setup_database.py bookstore.sql bookstore.csv templates static .env.example README.md test_app.py
   git commit -m "Complete bookstore app and reproducible database setup"
   git push origin your-branch-name
   ```

   Review the changed-file list first. Never add `.env`, `venv`, backups, or real customer data.

## GROUP MEMBER SETUP — SIMPLE INSTRUCTIONS

Copy this section into Discord.

1. Open PowerShell. Download the project the first time:

   ```powershell
   cd "$HOME\Documents"
   git clone https://github.com/RomanOglan/Bookstore-Management-System.git
   cd .\Bookstore-Management-System
   code .
   ```

   If you already cloned it, do not clone again. Open your existing folder and run:

   ```powershell
   git status
   git pull --ff-only
   code .
   ```

   If `git status` shows your own unfinished changes, commit them on your branch before pulling. Do not erase them.

2. Create and activate the Python environment (first time only):

   ```powershell
   py -m venv venv
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

   On later days, only run:

   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

3. Create your private local settings (first time only):

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Put your own local MySQL username/password in `.env`, save it, and never commit that file.

4. Make sure your local MySQL 8.0 server is running. Import the complete schema and every record currently in `bookstore.csv`:

   ```powershell
   python setup_database.py
   ```

   This safe command can be run again after updates. It does not delete your existing orders, loans, quantities, or extra books.

5. Test and start the website:

   ```powershell
   python -m unittest -v
   python app.py
   ```

6. Open these pages:

   - <http://127.0.0.1:5001/dbtest> — confirms MySQL and the imported CSV count
   - <http://127.0.0.1:5001> — catalog and search

   Demo customer login: `customer@bookstore.local` / `Customer123!`

   Demo staff login: `staff@bookstore.local` / `Staff123!`

7. To test purchasing, sign in as Staff, edit a book, and set a numeric sale quantity. Sign in as Customer and buy it. Confirm the quantity falls and the order appears under **My orders**.

8. To test borrowing, sign in as Staff, open a book, and add a unique lendable copy barcode. Sign in as Customer and borrow it. Sign back in as Staff under **Manage loans** to return it.

9. For future team updates, save your work on your own branch, then pull safely:

   ```powershell
   git status
   git add .
   git commit -m "Describe my changes"
   git pull --rebase origin main
   python setup_database.py
   ```

   Check `git status` before `git add .` and make sure `.env`, `venv`, and database backups are not listed.

10. Important: everyone has a separate MySQL database. Git synchronizes project files only. A book, order, loan, or quantity changed on one computer does **not** automatically change anyone else's database. Share approved database changes through reviewed setup/seed/migration files in Git, then each person runs them locally.

## Remaining source-data limitations

- ISBN, author, description, and exact quantities cannot be recovered from the checked-in CSV because those columns do not exist there.
- The project requirement mentions typo-tolerant search and overdue fees. Current search handles case, extra spaces, and partial matches; true spelling correction and fees require an agreed rule/data model and are not invented here.
- Concurrency and sub-500 ms performance targets require load testing on the team's actual MySQL computers; unit tests alone cannot prove them.
