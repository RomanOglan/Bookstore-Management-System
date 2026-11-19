import os
import secrets
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from mysql.connector import Error
from werkzeug.security import check_password_hash

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
        price = Decimal(form.get("price", ""))
    except InvalidOperation:
        raise ValueError("Price must be a number.")
    if not price.is_finite() or price < 0:
        raise ValueError("Price cannot be negative.")
    quantity_text = form.get("quantity", "").strip()
    quantity = None if not quantity_text else int(quantity_text)
    if quantity is not None and quantity < 0:
        raise ValueError("Quantity cannot be negative.")
    if quantity is not None and quantity > 65535:
        raise ValueError("Quantity cannot exceed 65535.")
    category_id = int(form.get("category_id", ""))
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


@app.post("/logout")
@login_required
def logout():
    require_csrf()
    session.clear()
    return redirect(url_for("home"))


@app.post("/book/<int:book_id>/buy")
@login_required
def buy_book(book_id):
    require_csrf()
    try:
        quantity = positive_int(request.form.get("quantity"))
        delivery = request.form.get("delivery")
        if delivery not in {"Delivery", "Pick-Up"}:
            raise ValueError("Choose Delivery or Pick-Up.")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("book_detail", book_id=book_id))

    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        conn.start_transaction()
        cur.execute("SELECT Price, Quantity FROM Books WHERE BookID=%s FOR UPDATE", (book_id,))
        book = cur.fetchone()
        if not book or book["Quantity"] is None or book["Quantity"] < quantity:
            raise ValueError("That quantity is not available for purchase.")
        cur.execute("INSERT INTO Orders (DeliveryType, UserID) VALUES (%s, %s)", (delivery, session["user_id"]))
        order_id = cur.lastrowid
        cur.execute("INSERT INTO Order_Items (BookID, OrderID, Quantity, Price) VALUES (%s,%s,%s,%s)",
                    (book_id, order_id, quantity, book["Price"]))
        cur.execute("UPDATE Books SET Quantity=Quantity-%s WHERE BookID=%s", (quantity, book_id))
        conn.commit()
        flash(f"Order #{order_id} placed.", "success")
    except ValueError as exc:
        conn.rollback()
        flash(str(exc), "error")
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("book_detail", book_id=book_id))


@app.post("/book/<int:book_id>/borrow")
@login_required
def borrow_book(book_id):
    require_csrf()
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        conn.start_transaction()
        cur.execute("SELECT COUNT(*) AS count FROM Loans WHERE UserID=%s AND LoanStatus IN ('On-Loan','Late')", (session["user_id"],))
        if cur.fetchone()["count"] >= 5:
            raise ValueError("The borrowing limit is five active loans.")
        cur.execute("SELECT CopyID FROM Book_Copies WHERE BookID=%s AND CopyStatus='Available' ORDER BY CopyID LIMIT 1 FOR UPDATE", (book_id,))
        copy = cur.fetchone()
        if not copy:
            raise ValueError("No lendable copy is currently available.")
        cur.execute("""INSERT INTO Loans (UserID, CopyID, BorrowedDate, DueDate, LoanStatus)
                       VALUES (%s,%s,CURDATE(),DATE_ADD(CURDATE(), INTERVAL 14 DAY),'On-Loan')""",
                    (session["user_id"], copy["CopyID"]))
        cur.execute("UPDATE Book_Copies SET CopyStatus='On-Loan' WHERE CopyID=%s", (copy["CopyID"],))
        conn.commit()
        flash("Book borrowed for 14 days.", "success")
    except ValueError as exc:
        conn.rollback()
        flash(str(exc), "error")
    except Error:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("book_detail", book_id=book_id))


@app.route("/orders")
@login_required
def orders():
    rows = query_all(
        """SELECT o.OrderID, o.OrderDate, o.DeliveryType,
                  SUM(oi.Quantity * oi.Price) AS Total
             FROM Orders o JOIN Order_Items oi ON o.OrderID=oi.OrderID
            WHERE o.UserID=%s GROUP BY o.OrderID, o.OrderDate, o.DeliveryType
            ORDER BY o.OrderDate DESC""", (session["user_id"],))
    return render_template("orders.html", orders=rows)


@app.route("/loans")
@login_required
def loans():
    rows = query_all(
        """SELECT l.LoanID, b.Title, bc.Barcode, l.BorrowedDate, l.DueDate,
                  l.ReturnedDate, l.LoanStatus
             FROM Loans l JOIN Book_Copies bc ON l.CopyID=bc.CopyID
             JOIN Books b ON bc.BookID=b.BookID WHERE l.UserID=%s ORDER BY l.DueDate DESC""",
        (session["user_id"],))
    return render_template("loans.html", loans=rows)


@app.route("/admin/books")
@staff_required
def admin_books():
    books = query_all("SELECT BookID, ISBN, Title, Price, Quantity FROM Books ORDER BY Title LIMIT 200")
    return render_template("admin_books.html", books=books)


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
    book = query_one("SELECT * FROM Books WHERE BookID=%s", (book_id,))
    if not book:
        abort(404)
    categories = query_all("SELECT CategoryID, CategoryName FROM Category ORDER BY CategoryName")
    if request.method == "POST":
        require_csrf()
        try:
            values = book_form_values(request.form)
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""UPDATE Books SET Title=%s, ISBN=%s, Description=%s, Price=%s,
                               Quantity=%s, CategoryID=%s WHERE BookID=%s""", (*values, book_id))
                conn.commit(); cur.close()
            finally:
                conn.close()
            flash("Book updated.", "success")
            return redirect(url_for("book_detail", book_id=book_id))
        except (ValueError, TypeError) as exc:
            flash(str(exc), "error")
    return render_template("book_form.html", book=book, categories=categories)


@app.post("/admin/book/<int:book_id>/delete")
@staff_required
def delete_book(book_id):
    require_csrf()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM Books WHERE BookID=%s", (book_id,))
        conn.commit()
        flash("Book deleted.", "success")
    except Error as exc:
        conn.rollback()
        if exc.errno == 1451:
            flash("This book has order, loan, or copy history and cannot be deleted.", "error")
        else:
            raise
    finally:
        cur.close(); conn.close()
    return redirect(url_for("admin_books"))


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
    if not barcode or len(barcode) > 50:
        flash("Enter a barcode up to 50 characters.", "error")
    else:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO Book_Copies (Barcode, BookID) VALUES (%s,%s)", (barcode, book_id))
            conn.commit(); cur.close()
            flash("Lendable copy added.", "success")
        finally:
            conn.close()
    return redirect(url_for("book_detail", book_id=book_id))


@app.route("/admin/loans")
@staff_required
def admin_loans():
    rows = query_all(
        """SELECT l.LoanID, u.Name, b.Title, bc.Barcode, l.DueDate, l.LoanStatus
             FROM Loans l JOIN Users u ON l.UserID=u.UserID JOIN Book_Copies bc ON l.CopyID=bc.CopyID
             JOIN Books b ON bc.BookID=b.BookID WHERE l.LoanStatus IN ('On-Loan','Late') ORDER BY l.DueDate""")
    return render_template("admin_loans.html", loans=rows)


@app.post("/admin/loan/<int:loan_id>/return")
@staff_required
def return_loan(loan_id):
    require_csrf()
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True); conn.start_transaction()
        cur.execute("SELECT CopyID, LoanStatus FROM Loans WHERE LoanID=%s FOR UPDATE", (loan_id,))
        loan = cur.fetchone()
        if not loan or loan["LoanStatus"] == "Returned":
            raise ValueError("That loan is not active.")
        cur.execute("UPDATE Loans SET ReturnedDate=CURDATE(), LoanStatus='Returned' WHERE LoanID=%s", (loan_id,))
        cur.execute("UPDATE Book_Copies SET CopyStatus='Available' WHERE CopyID=%s", (loan["CopyID"],))
        conn.commit(); flash("Book returned.", "success")
    except ValueError as exc:
        conn.rollback(); flash(str(exc), "error")
    finally:
        cur.close(); conn.close()
    return redirect(url_for("admin_loans"))


@app.route("/dbtest")
def dbtest():
    counts = query_one("SELECT COUNT(*) AS books, SUM(SourceURL IS NOT NULL) AS imported FROM Books")
    return render_template("dbtest.html", count=counts["books"], imported=counts["imported"])


if __name__ == "__main__":
    app.run(port=int(os.getenv("FLASK_PORT", "5001")), debug=os.getenv("FLASK_DEBUG") == "1")
