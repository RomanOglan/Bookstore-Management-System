import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

import app


class ValidationTests(unittest.TestCase):
    def test_all_templates_compile(self):
        for template in (Path(__file__).parent / "templates").glob("*.html"):
            app.app.jinja_env.get_template(template.name)

    def test_positive_integer_validation(self):
        self.assertEqual(app.positive_int("2"), 2)
        for value in ("0", "-1", "two", None):
            with self.assertRaises(ValueError):
                app.positive_int(value)

    def test_book_form_validation(self):
        values = app.book_form_values(MultiDict({
            "title": "A Book", "isbn": "1234567890", "description": "",
            "price": "12.50", "quantity": "3", "category_id": "1",
        }))
        self.assertEqual(values, ("A Book", "1234567890", None, Decimal("12.50"), 3, 1))
        for invalid_price in ("NaN", "Infinity", "-0.01"):
            form = MultiDict({"title": "A Book", "price": invalid_price, "category_id": "1"})
            with self.assertRaises(ValueError):
                app.book_form_values(form)

    def test_staff_page_rejects_customer(self):
        app.app.config.update(TESTING=True, SECRET_KEY="test")
        with app.app.test_client() as client:
            with client.session_transaction() as session:
                session.update(user_id=1, role="Customer")
            self.assertEqual(client.get("/admin/books").status_code, 403)

    def test_catalog_search_calls_stored_procedure(self):
        app.app.config.update(TESTING=True, SECRET_KEY="test")
        with patch.object(app, "call_procedure", return_value=[[{"total": 0}], []]) as proc, \
             patch.object(app, "query_all", return_value=[]):
            response = app.app.test_client().get("/?q=  harry   potter  ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(proc.call_args.args[0], "SearchBooks")
        self.assertEqual(proc.call_args.args[1][0], "harry potter")

    def staff_client(self):
        app.app.config.update(TESTING=True, SECRET_KEY="test")
        client = app.app.test_client()
        with client.session_transaction() as session:
            session.update(user_id=1, role="Staff", csrf_token="tok")
        return client

    def test_staff_inventory_uses_search_procedure_with_paging(self):
        client = self.staff_client()
        with patch.object(app, "call_procedure", return_value=[[{"total": 120}], []]) as proc, \
             patch.object(app, "query_all", return_value=[]):
            response = client.get("/admin/books?q=  dune  &page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(proc.call_args.args, ("SearchBooks", ("dune", None, 50, 50)))
        self.assertIn(b"Page 2 of 3", response.data)

    def test_restock_calls_procedure(self):
        client = self.staff_client()
        with patch.object(app, "call_procedure", return_value=[[{"NewQuantity": 12}]]) as proc:
            response = client.post("/admin/book/5/restock", data={"amount": "7", "csrf_token": "tok"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proc.call_args.args, ("RestockBook", (5, 7)))

    def test_restock_rejects_bad_amount(self):
        client = self.staff_client()
        with patch.object(app, "call_procedure") as proc:
            client.post("/admin/book/5/restock", data={"amount": "-3", "csrf_token": "tok"})
        proc.assert_not_called()

    def test_add_book_shows_procedure_error(self):
        client = self.staff_client()
        error = app.Error(msg="A book with that ISBN already exists", errno=1644)
        form = {"title": "A Book", "isbn": "1234567890", "price": "9.99", "quantity": "3",
                "category_id": "1", "author": "Some Author", "csrf_token": "tok"}
        with patch.object(app, "query_all", return_value=[{"CategoryID": 1, "CategoryName": "Fiction"}]), \
             patch.object(app, "call_procedure", side_effect=error) as proc:
            response = client.post("/admin/book/new", data=form)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already exists", response.data)
        self.assertEqual(proc.call_args.args[1][-1], "Some Author")
    def client_as(self, role):
        app.app.config.update(TESTING=True, SECRET_KEY="test")
        client = app.app.test_client()
        with client.session_transaction() as session:
            session["csrf_token"] = "tok"
            if role:
                session.update(user_id=1, role=role, name="Tester")
        return client

    def test_friendly_number_errors(self):
        base = {"title": "A Book", "price": "9.99", "quantity": "3", "category_id": "1"}
        for field, bad, text in (("price", "abc", "Price must be a number"),
                                 ("quantity", "x", "Quantity must be a whole number"),
                                 ("category_id", "", "Choose a category")):
            with self.assertRaises(ValueError) as ctx:
                app.book_form_values(MultiDict({**base, field: bad}))
            self.assertIn(text, str(ctx.exception))

    def test_edit_book_calls_update_procedure_and_shows_error(self):
        client = self.staff_client()
        book = {"BookID": 5, "Title": "Old", "ISBN": None, "Description": None, "Price": Decimal("5"),
                "Quantity": 1, "CategoryID": 1, "AuthorName": None}
        form = {"title": "New", "isbn": "1234567890", "price": "9.99", "quantity": "3",
                "category_id": "1", "author": "Some Author", "csrf_token": "tok"}
        with patch.object(app, "query_one", return_value=book), \
             patch.object(app, "query_all", return_value=[{"CategoryID": 1, "CategoryName": "Fiction"}]):
            with patch.object(app, "call_procedure", return_value=[[{"BookID": 5}]]) as proc:
                response = client.post("/admin/book/5/edit", data=form)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(proc.call_args.args[0], "UpdateBook")
            self.assertEqual(proc.call_args.args[1][0], 5)
            self.assertEqual(proc.call_args.args[1][-1], "Some Author")
            error = app.Error(msg="Another book already uses that ISBN", errno=1644)
            with patch.object(app, "call_procedure", side_effect=error):
                response = client.post("/admin/book/5/edit", data=form)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Another book already uses that ISBN", response.data)

    def test_add_copy_duplicate_barcode_message(self):
        client = self.staff_client()
        error = app.Error(msg="That barcode is already in use", errno=1644)
        with patch.object(app, "call_procedure", side_effect=error) as proc:
            response = client.post("/admin/book/5/copy", data={"barcode": "BC-1", "csrf_token": "tok"},
                                   follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proc.call_args.args, ("AddBookCopy", (5, "BC-1")))
        with client.session_transaction() as session:
            self.assertIn("That barcode is already in use", [m for _, m in session["_flashes"]])

    def test_delete_book_uses_procedure_and_reports_block(self):
        client = self.staff_client()
        with patch.object(app, "call_procedure", return_value=[[{"DeletedBookID": 5}]]) as proc:
            response = client.post("/admin/book/5/delete", data={"csrf_token": "tok"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proc.call_args.args, ("DeleteBook", (5,)))
        error = app.Error(msg="This book appears in past orders and cannot be deleted", errno=1644)
        with patch.object(app, "call_procedure", side_effect=error):
            response = client.post("/admin/book/5/delete", data={"csrf_token": "tok"})
        self.assertIn("/admin/book/5/edit", response.headers["Location"])

    def test_low_stock_page_staff_only_and_calls_procedure(self):
        self.assertEqual(self.client_as("Customer").get("/admin/low-stock").status_code, 403)
        client = self.staff_client()
        rows = [{"BookID": 1, "Title": "Tiny Stock", "Quantity": 1, "AuthorName": None, "CategoryName": "Fiction"}]
        with patch.object(app, "call_procedure", return_value=[rows]) as proc:
            response = client.get("/admin/low-stock?threshold=5&q=%20tiny%20%20stock%20")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(proc.call_args.args, ("LowStockReport", (5, "tiny stock")))
        self.assertIn(b"Tiny Stock", response.data)

    def test_borrow_calls_procedure_and_shows_error(self):
        client = self.client_as("Customer")
        with patch.object(app, "call_procedure", return_value=[[{"NewLoanID": 9}]]) as proc:
            response = client.post("/book/5/borrow", data={"csrf_token": "tok"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proc.call_args.args, ("BorrowBook", (1, 5)))
        error = app.Error(msg="Return your overdue books before borrowing more", errno=1644)
        with patch.object(app, "call_procedure", side_effect=error):
            client.post("/book/5/borrow", data={"csrf_token": "tok"})
        with client.session_transaction() as session:
            self.assertIn("Return your overdue books before borrowing more", [m for _, m in session["_flashes"]])

    def test_customer_return_passes_own_user_id(self):
        client = self.client_as("Customer")
        result = [[{"LoanID": 3, "DaysLate": 4, "LateFee": Decimal("1.00")}]]
        with patch.object(app, "call_procedure", return_value=result) as proc:
            response = client.post("/loan/3/return", data={"csrf_token": "tok"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proc.call_args.args, ("ReturnBook", (3, 1)))
        with client.session_transaction() as session:
            self.assertIn("Book returned 4 day(s) late. Late fee: $1.00.", [m for _, m in session["_flashes"]])

    def test_staff_return_uses_no_owner_and_loan_filter_is_whitelisted(self):
        client = self.staff_client()
        result = [[{"LoanID": 3, "DaysLate": 0, "LateFee": Decimal("0.00")}]]
        with patch.object(app, "call_procedure", return_value=result) as proc:
            client.post("/admin/loan/3/return", data={"csrf_token": "tok"})
        self.assertEqual(proc.call_args.args, ("ReturnBook", (3, None)))
        with patch.object(app, "call_procedure", return_value=[[{"MarkedLate": 0}]]) as proc, \
             patch.object(app, "query_all", return_value=[]) as query:
            response = client.get("/admin/loans?status=late;DROP")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(proc.call_args.args[0], "MarkOverdueLoans")
        self.assertIn("l.LoanStatus IN ('On-Loan', 'Late')", query.call_args.args[0])
        with patch.object(app, "call_procedure", return_value=[[{"MarkedLate": 0}]]), \
             patch.object(app, "query_all", return_value=[]) as query:
            client.get("/admin/loans?status=late")
        self.assertIn("l.LoanStatus = 'Late'", query.call_args.args[0])

    def test_loans_page_shows_fee_total(self):
        client = self.client_as("Customer")
        rows = [{"LoanID": 1, "Name": "T", "Title": "Late Book", "Barcode": "B1", "BorrowedDate": "2026-10-01",
                 "DueDate": "2026-10-15", "ReturnedDate": None, "LoanStatus": "Late", "Fee": Decimal("1.50")}]
        with patch.object(app, "call_procedure", return_value=[[{"MarkedLate": 0}]]), \
             patch.object(app, "query_all", return_value=rows):
            response = client.get("/loans")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Late fees: $1.50", response.data)

    def test_dbtest_is_staff_only(self):
        self.assertEqual(self.client_as(None).get("/dbtest").status_code, 302)
        self.assertEqual(self.client_as("Customer").get("/dbtest").status_code, 403)
        with patch.object(app, "query_one", return_value={"books": 3, "imported": 3}):
            self.assertEqual(self.client_as("Staff").get("/dbtest").status_code, 200)

    def test_only_customers_can_buy(self):
        data = {"quantity": "0", "delivery": "Delivery", "csrf_token": "tok"}
        self.assertEqual(self.client_as("Staff").post("/book/1/buy", data=data).status_code, 403)
        self.assertEqual(self.client_as(None).post("/book/1/buy", data=data).status_code, 302)
        # a customer is allowed through; quantity 0 is rejected before any database call
        self.assertEqual(self.client_as("Customer").post("/book/1/buy", data=data).status_code, 302)

    def test_register_rejects_bad_input_without_touching_database(self):
        bad = [
            {"name": "", "email": "a@b.com", "password": "longenough", "confirm": "longenough"},
            {"name": "Ann", "email": "not-an-email", "password": "longenough", "confirm": "longenough"},
            {"name": "Ann", "email": "a@b.com", "password": "short", "confirm": "short"},
            {"name": "Ann", "email": "a@b.com", "password": "longenough", "confirm": "different1"},
        ]
        with patch.object(app, "get_connection", side_effect=AssertionError("database used")):
            for form in bad:
                response = self.client_as(None).post("/register", data={**form, "csrf_token": "tok"})
                self.assertEqual(response.status_code, 200)

    def test_register_creates_customer_with_hashed_password(self):
        calls = []

        class Cursor:
            def execute(self, sql, params):
                calls.append((sql, params))
            def close(self):
                pass

        class Conn:
            def cursor(self):
                return Cursor()
            def commit(self):
                pass
            def rollback(self):
                pass
            def close(self):
                pass

        client = self.client_as(None)
        form = {"name": "Ann", "email": " Ann@Example.com ", "password": "longenough",
                "confirm": "longenough", "csrf_token": "tok"}
        with patch.object(app, "get_connection", return_value=Conn()):
            response = client.post("/register", data=form)
        self.assertEqual(response.status_code, 302)
        sql, params = calls[0]
        self.assertIn("'Customer'", sql)
        self.assertEqual(params[1], "ann@example.com")
        self.assertNotEqual(params[2], "longenough")

    def test_register_duplicate_email_message(self):
        class Cursor:
            def execute(self, sql, params):
                raise app.Error(msg="dup", errno=1062)
            def close(self):
                pass

        class Conn:
            def cursor(self):
                return Cursor()
            def rollback(self):
                pass
            def close(self):
                pass

        form = {"name": "Ann", "email": "a@b.com", "password": "longenough",
                "confirm": "longenough", "csrf_token": "tok"}
        with patch.object(app, "get_connection", return_value=Conn()):
            response = self.client_as(None).post("/register", data=form)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already registered", response.data)


if __name__ == "__main__":
    unittest.main()
