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
