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

if __name__ == "__main__":
    unittest.main()
