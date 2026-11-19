import os
import re
import secrets
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_connection

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")


def query_all(sql, params=()):
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def query_one(sql, params=()):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def call_procedure(name, args=()):
    """Call a stored procedure and return its result sets as a list of lists of dicts."""
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.callproc(name, args)
        results = [result.fetchall() for result in cur.stored_results()]
        conn.commit()
        cur.close()
        return results
    finally:
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in first.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "Staff":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in first.", "error")
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "Customer":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def require_csrf():
    if not secrets.compare_digest(session.get("csrf_token", ""), request.form.get("csrf_token", "")):
        abort(400, "Invalid form token. Refresh the page and try again.")


def positive_int(value, label="Quantity"):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")
    if result <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return result


def book_form_values(form):
    title = form.get("title", "").strip()
    isbn = form.get("isbn", "").strip() or None
    description = form.get("description", "").strip() or None
    if not title:
        raise ValueError("Title is required.")
    if isbn and (not isbn.isdigit() or len(isbn) not in {10, 13}):
        raise ValueError("ISBN must contain exactly 10 or 13 digits.")
    try:
        price = Decimal(form.get("price", "").strip())
    except InvalidOperation:
        raise ValueError("Price must be a number, for example 12.99.")
    if not price.is_finite():
        raise ValueError("Price must be a number, for example 12.99.")
    if price < 0:
        raise ValueError("Price cannot be negative.")
    if price >= 100000000:
        raise ValueError("Price is too large.")
    quantity_text = form.get("quantity", "").strip()
    try:
        quantity = None if not quantity_text else int(quantity_text)
    except ValueError:
        raise ValueError("Quantity must be a whole number.")
    if quantity is not None and quantity < 0:
        raise ValueError("Quantity cannot be negative.")
    if quantity is not None and quantity > 65535:
        raise ValueError("Quantity cannot exceed 65535.")
    try:
        category_id = int(form.get("category_id", ""))
    except ValueError:
        raise ValueError("Choose a category.")
    return title, isbn, description, price, quantity, category_id


@app.context_processor
def template_context():
    return {"csrf_token": csrf_token}


@app.errorhandler(Error)
def database_error(exc):
    app.logger.exception("Database error")
    return render_template("error.html", message="The database could not complete that request."), 500


@app.route("/")
def home():
    search = " ".join(request.args.get("q", "").split())
    category = request.args.get("category", type=int)
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 24
    results = call_procedure("SearchBooks", (search, category, per_page, (page - 1) * per_page))
    count = results[0][0]["total"]
    books = results[1] if len(results) > 1 else []
    categories = query_all("SELECT CategoryID, CategoryName FROM Category ORDER BY CategoryName")
    return render_template("home.html", books=books, categories=categories, total=count,
                           page=page, pages=max((count + per_page - 1) // per_page, 1),
                           search=search, selected_category=category)


@app.route("/book/<int:book_id>")
def book_detail(book_id):
    book = query_one(
        """SELECT b.*, a.AuthorName, c.CategoryName,
                  SUM(bc.CopyStatus='Available') AS AvailableCopies
             FROM Books b LEFT JOIN Author a ON b.AuthorID=a.AuthorID
             LEFT JOIN Category c ON b.CategoryID=c.CategoryID
             LEFT JOIN Book_Copies bc ON b.BookID=bc.BookID
            WHERE b.BookID=%s GROUP BY b.BookID, a.AuthorName, c.CategoryName""",
        (book_id,),
    )
    if not book:
        abort(404)
    return render_template("book_detail.html", book=book)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        require_csrf()
        email = request.form.get("email", "").strip().lower()
        user = query_one("SELECT * FROM Users WHERE Email=%s", (email,))
        if not user or user["AccountStatus"] != "Active" or not check_password_hash(user["PasswordHash"], request.form.get("password", "")):
            flash("Email or password is incorrect, or the account is inactive.", "error")
        else:
            session.clear()
            session.update(user_id=user["UserID"], name=user["Name"], role=user["Role"])
            csrf_token()
            next_url = request.args.get("next", "")
            return redirect(next_url if next_url.startswith("/") and not next_url.startswith("//") else url_for("home"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        require_csrf()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        problem = None
        if not name or len(name) > 100:
            problem = "Enter your name (100 characters or fewer)."
        elif len(email) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            problem = "Enter a valid email address."
        elif len(password) < 8:
            problem = "Password must be at least 8 characters."
        elif password != request.form.get("confirm", ""):
            problem = "The two passwords do not match."
        if problem:
            flash(problem, "error")
        else:
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO Users (Name, Email, PasswordHash, Role, AccountStatus) "
                    "VALUES (%s, %s, %s, 'Customer', 'Active')",
                    (name, email, generate_password_hash(password)),
                )
                conn.commit()
                cur.close()
            except Error as exc:
                conn.rollback()
                if exc.errno != 1062:
                    raise
                flash("That email is already registered.", "error")
            else:
                flash("Account created. Please sign in.", "success")
                return redirect(url_for("login"))
            finally:
                conn.close()
    return render_template("register.html")


@app.post("/logout")
@login_required
def logout():
    require_csrf()
    session.clear()
    return redirect(url_for("home"))


@app.post("/book/<int:book_id>/buy")
@customer_required
def buy_book(book_id):
    require_csrf()
    try:
        quantity = positive_int(request.form.get("quantity"))
        delivery = request.form.get("delivery")
        if delivery not in {"Delivery", "Pick-Up"}:
            raise ValueError("Choose Delivery or Pick-Up.")
        # PlaceOrder locks the book row, checks stock, records the price at purchase,
        # lowers the stock and commits, all in one transaction.
        result = call_procedure("PlaceOrder", (session["user_id"], book_id, quantity, delivery))
        order_id = result[0][0]["NewOrderID"]
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("book_detail", book_id=book_id))
    except Error as exc:
        if exc.errno != 1644:
            raise
        flash(order_error_message(exc.msg, book_id, quantity), "error")
        return redirect(url_for("book_detail", book_id=book_id))
    flash(f"Order #{order_id} placed.", "success")
    return redirect(url_for("order_detail", order_id=order_id))


def order_error_message(message, book_id, quantity):
    """Make PlaceOrder's out-of-stock error say how many copies are left."""
    if message != "Book unavailable or insufficient stock":
        return message
    book = query_one("SELECT Title, Quantity FROM Books WHERE BookID=%s", (book_id,))
    if not book or book["Quantity"] is None:
        return "That book is not available for purchase."
    if book["Quantity"] == 0:
        return f"Sorry, {book['Title']} is out of stock."
    return (f"Only {book['Quantity']} of {book['Title']} left in stock, "
            f"but you asked for {quantity}.")


@app.post("/book/<int:book_id>/borrow")
@login_required
def borrow_book(book_id):
    require_csrf()
    try:
        call_procedure("BorrowBook", (session["user_id"], book_id))
        flash("Book borrowed for 14 days.", "success")
    except Error as exc:
        if exc.errno != 1644:
            raise
        flash(exc.msg, "error")
    return redirect(url_for("book_detail", book_id=book_id))


@app.route("/orders")
@login_required
def orders():
    rows = query_all(
        """SELECT o.OrderID, o.OrderDate, o.DeliveryType,
                  SUM(oi.Quantity * oi.Price) AS Total
             FROM Orders o JOIN Order_Items oi ON o.OrderID=oi.OrderID
            WHERE o.UserID=%s GROUP BY o.OrderID, o.OrderDate, o.DeliveryType
            ORDER BY o.OrderDate DESC, o.OrderID DESC""", (session["user_id"],))
    return render_template("orders.html", orders=rows)


@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order = query_one(
        """SELECT o.OrderID, o.OrderDate, o.DeliveryType, o.UserID, u.Name, u.Email
             FROM Orders o JOIN Users u ON o.UserID=u.UserID
            WHERE o.OrderID=%s""", (order_id,))
    # Customers see only their own orders; staff see any. A missing order and
    # someone else's order both give 404, so order numbers can't be probed.
    if not order or (session.get("role") != "Staff" and order["UserID"] != session["user_id"]):
        abort(404)
    items = query_all(
        """SELECT oi.BookID, b.Title, oi.Quantity, oi.Price,
                  oi.Quantity * oi.Price AS LineTotal
             FROM Order_Items oi JOIN Books b ON oi.BookID=b.BookID
            WHERE oi.OrderID=%s ORDER BY b.Title""", (order_id,))
    total = sum(item["LineTotal"] for item in items)
    return render_template("order_detail.html", order=order, items=items, total=total)


LOAN_SELECT = """SELECT l.LoanID, u.Name, b.Title, bc.Barcode, l.BorrowedDate, l.DueDate,
                        l.ReturnedDate, l.LoanStatus,
                        CASE WHEN l.LoanStatus = 'Returned' THEN l.LateFee
                             WHEN l.DueDate < CURDATE() THEN DATEDIFF(CURDATE(), l.DueDate) * %s
                             ELSE 0 END AS Fee
                   FROM Loans l
                   JOIN Users u ON l.UserID = u.UserID
                   JOIN Book_Copies bc ON l.CopyID = bc.CopyID
                   JOIN Books b ON bc.BookID = b.BookID"""
LATE_FEE_PER_DAY = Decimal("0.25")


@app.route("/loans")
@login_required
def loans():
    call_procedure("MarkOverdueLoans", ())
    rows = query_all(LOAN_SELECT + " WHERE l.UserID=%s ORDER BY l.LoanStatus = 'Returned', l.DueDate DESC",
                     (LATE_FEE_PER_DAY, session["user_id"]))
    owed = sum((row["Fee"] for row in rows), Decimal("0"))
    return render_template("loans.html", loans=rows, owed=owed)


@app.post("/loan/<int:loan_id>/return")
@login_required
def return_own_loan(loan_id):
    require_csrf()
    flash_return(call_procedure_or_flash("ReturnBook", (loan_id, session["user_id"])))
    return redirect(url_for("loans"))


def call_procedure_or_flash(name, args):
    try:
        return call_procedure(name, args)
    except Error as exc:
        if exc.errno != 1644:
            raise
        flash(exc.msg, "error")
        return None


def flash_return(results):
    if results:
        row = results[0][0]
        if row["DaysLate"]:
            flash(f"Book returned {row['DaysLate']} day(s) late. Late fee: ${row['LateFee']}.", "success")
        else:
            flash("Book returned on time.", "success")


@app.route("/admin/books")
@staff_required
def admin_books():
    search = " ".join(request.args.get("q", "").split())[:100]
    category = request.args.get("category", type=int)
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 50
    results = call_procedure("SearchBooks", (search, category, per_page, (page - 1) * per_page))
    count = results[0][0]["total"]
    books = results[1] if len(results) > 1 else []
    categories = query_all("SELECT CategoryID, CategoryName FROM Category ORDER BY CategoryName")
    return render_template("admin_books.html", books=books, categories=categories, total=count,
                           page=page, pages=max((count + per_page - 1) // per_page, 1),
                           search=search, selected_category=category)


@app.route("/admin/book/new", methods=["GET", "POST"])
@staff_required
def add_book():
    categories = query_all("SELECT CategoryID, CategoryName FROM Category ORDER BY CategoryName")
    if request.method == "POST":
        require_csrf()
        try:
            values = book_form_values(request.form)
            author = request.form.get("author", "").strip()[:100] or None
            book_id = call_procedure("AddBook", (*values, author))[0][0]["NewBookID"]
            flash("Book created.", "success")
            return redirect(url_for("book_detail", book_id=book_id))
        except (ValueError, TypeError) as exc:
            flash(str(exc), "error")
        except Error as exc:
            if exc.errno != 1644:
                raise
            flash(exc.msg, "error")
    return render_template("book_form.html", book=None, categories=categories)


@app.route("/admin/book/<int:book_id>/edit", methods=["GET", "POST"])
@staff_required
def edit_book(book_id):
    book = query_one(
        """SELECT b.*, a.AuthorName FROM Books b
             LEFT JOIN Author a ON a.AuthorID = b.AuthorID WHERE b.BookID=%s""", (book_id,))
    if not book:
        abort(404)
    categories = query_all("SELECT CategoryID, CategoryName FROM Category ORDER BY CategoryName")
    if request.method == "POST":
        require_csrf()
        try:
            values = book_form_values(request.form)
            author = request.form.get("author", "").strip()[:100] or None
            call_procedure("UpdateBook", (book_id, *values, author))
            flash("Book updated.", "success")
            return redirect(url_for("book_detail", book_id=book_id))
        except (ValueError, TypeError) as exc:
            flash(str(exc), "error")
        except Error as exc:
            if exc.errno != 1644:
                raise
            flash(exc.msg, "error")
    return render_template("book_form.html", book=book, categories=categories)


@app.post("/admin/book/<int:book_id>/delete")
@staff_required
def delete_book(book_id):
    require_csrf()
    try:
        call_procedure("DeleteBook", (book_id,))
        flash("Book deleted.", "success")
    except Error as exc:
        if exc.errno != 1644:
            raise
        flash(exc.msg, "error")
        return redirect(url_for("edit_book", book_id=book_id))
    return redirect(url_for("admin_books"))


@app.route("/admin/low-stock")
@staff_required
def low_stock():
    threshold = request.args.get("threshold", 3, type=int)
    threshold = min(max(threshold, 0), 1000)
    search = " ".join(request.args.get("q", "").split())[:100]
    results = call_procedure("LowStockReport", (threshold, search))
    books = results[0] if results else []
    return render_template("low_stock.html", books=books, threshold=threshold, search=search)


@app.post("/admin/book/<int:book_id>/restock")
@staff_required
def restock_book(book_id):
    require_csrf()
    try:
        amount = positive_int(request.form.get("amount"), "Restock amount")
        result = call_procedure("RestockBook", (book_id, amount))[0][0]
        flash(f"Stock updated. New quantity: {result['NewQuantity']}.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except Error as exc:
        if exc.errno != 1644:
            raise
        flash(exc.msg, "error")
    return redirect(url_for("admin_books"))


@app.post("/admin/book/<int:book_id>/copy")
@staff_required
def add_copy(book_id):
    require_csrf()
    barcode = request.form.get("barcode", "").strip()
    if len(barcode) > 50:
        flash("Barcode can be at most 50 characters.", "error")
    else:
        try:
            call_procedure("AddBookCopy", (book_id, barcode))
            flash("Lendable copy added.", "success")
        except Error as exc:
            if exc.errno != 1644:
                raise
            flash(exc.msg, "error")
    return redirect(url_for("book_detail", book_id=book_id))


ORDER_PERIODS = {
    "today": ("Today", "o.OrderDate >= CURDATE()"),
    "week": ("Last 7 days", "o.OrderDate >= CURDATE() - INTERVAL 6 DAY"),
    "month": ("Last 30 days", "o.OrderDate >= CURDATE() - INTERVAL 29 DAY"),
    "all": ("All", "1 = 1"),
}


@app.route("/admin/orders")
@staff_required
def admin_orders():
    period = request.args.get("period", "all")
    if period not in ORDER_PERIODS:
        period = "all"
    search = " ".join(request.args.get("q", "").split())[:100]
    delivery = request.args.get("delivery", "")
    if delivery not in {"Delivery", "Pick-Up"}:
        delivery = ""
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 50

    where, params = [ORDER_PERIODS[period][1]], []
    if search:
        if search.lstrip("#").isdigit():
            where.append("o.OrderID = %s")
            params.append(int(search.lstrip("#")))
        else:
            where.append("(LOWER(u.Name) LIKE %s OR LOWER(u.Email) LIKE %s)")
            params += [f"%{search.lower()}%"] * 2
    if delivery:
        where.append("o.DeliveryType = %s")
        params.append(delivery)
    clause = " WHERE " + " AND ".join(where)

    summary = query_one(
        """SELECT COUNT(DISTINCT o.OrderID) AS Orders,
                  COALESCE(SUM(oi.Quantity), 0) AS Units,
                  COALESCE(SUM(oi.Quantity * oi.Price), 0) AS Revenue
             FROM Orders o JOIN Users u ON o.UserID=u.UserID
             JOIN Order_Items oi ON o.OrderID=oi.OrderID""" + clause, params)
    rows = query_all(
        """SELECT o.OrderID, o.OrderDate, o.DeliveryType, u.Name, u.Email,
                  SUM(oi.Quantity) AS Units,
                  SUM(oi.Quantity * oi.Price) AS Total
             FROM Orders o JOIN Users u ON o.UserID=u.UserID
             JOIN Order_Items oi ON o.OrderID=oi.OrderID""" + clause + """
            GROUP BY o.OrderID, o.OrderDate, o.DeliveryType, u.Name, u.Email
            ORDER BY o.OrderDate DESC, o.OrderID DESC
            LIMIT %s OFFSET %s""", [*params, per_page, (page - 1) * per_page])
    return render_template("admin_orders.html", orders=rows, summary=summary,
                           periods=ORDER_PERIODS, period=period, search=search,
                           delivery=delivery, page=page,
                           pages=max((summary["Orders"] + per_page - 1) // per_page, 1))


LOAN_FILTERS = {
    "active": "l.LoanStatus IN ('On-Loan', 'Late')",
    "late": "l.LoanStatus = 'Late'",
    "returned": "l.LoanStatus = 'Returned'",
    "all": "1 = 1",
}


@app.route("/admin/loans")
@staff_required
def admin_loans():
    status = request.args.get("status", "active")
    if status not in LOAN_FILTERS:
        status = "active"
    call_procedure("MarkOverdueLoans", ())
    rows = query_all(LOAN_SELECT + " WHERE " + LOAN_FILTERS[status] + " ORDER BY l.DueDate LIMIT 200",
                     (LATE_FEE_PER_DAY,))
    return render_template("admin_loans.html", loans=rows, status=status)


@app.post("/admin/loan/<int:loan_id>/return")
@staff_required
def return_loan(loan_id):
    require_csrf()
    flash_return(call_procedure_or_flash("ReturnBook", (loan_id, None)))
    return redirect(url_for("admin_loans"))


@app.route("/dbtest")
@staff_required
def dbtest():
    counts = query_one("SELECT COUNT(*) AS books, SUM(SourceURL IS NOT NULL) AS imported FROM Books")
    return render_template("dbtest.html", count=counts["books"], imported=counts["imported"])


if __name__ == "__main__":
    app.run(port=int(os.getenv("FLASK_PORT", "5001")), debug=os.getenv("FLASK_DEBUG") == "1")
