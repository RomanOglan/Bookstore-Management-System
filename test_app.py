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

    # ---- Orders ----
    ORDER = {"OrderID": 7, "OrderDate": "2026-11-19 14:30:00", "DeliveryType": "Pick-Up",
             "UserID": 1, "Name": "Demo Customer", "Email": "customer@bookstore.local"}
    ITEMS = [{"BookID": 3, "Title": "Sapiens", "Quantity": 2, "Price": Decimal("54.23"),
              "LineTotal": Decimal("108.46")}]

    def test_buy_calls_place_order_and_opens_order_page(self):
        client = self.client_as("Customer")
        data = {"quantity": "2", "delivery": "Pick-Up", "csrf_token": "tok"}
        with patch.object(app, "call_procedure", return_value=[[{"NewOrderID": 42}]]) as proc:
            response = client.post("/book/5/buy", data=data)
        self.assertEqual(proc.call_args.args, ("PlaceOrder", (1, 5, 2, "Pick-Up")))
        self.assertTrue(response.headers["Location"].endswith("/orders/42"))
        with client.session_transaction() as session:
            self.assertIn(("success", "Order #42 placed."), session["_flashes"])

    def test_buy_out_of_stock_shows_message(self):
        client = self.client_as("Customer")
        error = app.Error(msg="Book unavailable or insufficient stock", errno=1644)
        data = {"quantity": "9", "delivery": "Delivery", "csrf_token": "tok"}
        with patch.object(app, "call_procedure", side_effect=error), \
             patch.object(app, "query_one", return_value={"Title": "Sapiens", "Quantity": 3}):
            response = client.post("/book/5/buy", data=data)
        self.assertTrue(response.headers["Location"].endswith("/book/5"))
        with client.session_transaction() as session:
            message = session["_flashes"][0][1]
        self.assertIn("Only 3 of Sapiens left", message)

    def test_order_detail_shows_price_at_purchase_to_owner(self):
        with patch.object(app, "query_one", return_value=self.ORDER), \
             patch.object(app, "query_all", return_value=self.ITEMS):
            response = self.client_as("Customer").get("/orders/7")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"$54.23", response.data)
        self.assertIn(b"$108.46", response.data)

    def test_order_detail_hides_other_customers_orders(self):
        someone_else = {**self.ORDER, "UserID": 99}
        with patch.object(app, "query_one", return_value=someone_else), \
             patch.object(app, "query_all", return_value=self.ITEMS):
            self.assertEqual(self.client_as("Customer").get("/orders/7").status_code, 404)
        with patch.object(app, "query_one", return_value=None):
            self.assertEqual(self.client_as("Customer").get("/orders/999").status_code, 404)

    def test_staff_can_open_any_order(self):
        someone_else = {**self.ORDER, "UserID": 99}
        with patch.object(app, "query_one", return_value=someone_else), \
             patch.object(app, "query_all", return_value=self.ITEMS):
            response = self.client_as("Staff").get("/orders/7")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"customer@bookstore.local", response.data)

    def test_all_orders_page_is_staff_only(self):
        self.assertEqual(self.client_as("Customer").get("/admin/orders").status_code, 403)
        self.assertEqual(self.client_as(None).get("/admin/orders").status_code, 302)
        rows = [{"OrderID": 7, "OrderDate": "2026-11-19", "DeliveryType": "Pick-Up",
                 "Name": "Demo Customer", "Total": Decimal("108.46")}]
        with patch.object(app, "query_all", return_value=rows):
            response = self.client_as("Staff").get("/admin/orders")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Demo Customer", response.data)


if __name__ == "__main__":
    unittest.main()
