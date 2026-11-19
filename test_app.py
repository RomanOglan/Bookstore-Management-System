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

    def test_catalog_search_uses_parameters(self):
        app.app.config.update(TESTING=True, SECRET_KEY="test")
        with patch.object(app, "query_one", return_value={"total": 0}) as one, \
             patch.object(app, "query_all", side_effect=[[], []]) as all_rows:
            response = app.app.test_client().get("/?q=  harry   potter  ")
        self.assertEqual(response.status_code, 200)
        self.assertIn("harry potter", one.call_args.args[1][0])
        self.assertEqual(all_rows.call_count, 2)


if __name__ == "__main__":
    unittest.main()
