

USE Bookstore;

CREATE ROLE IF NOT EXISTS 'bookstore_customer', 'bookstore_staff';


GRANT SELECT ON Bookstore.Books TO 'bookstore_customer';
GRANT SELECT ON Bookstore.Author TO 'bookstore_customer';
GRANT SELECT ON Bookstore.Category TO 'bookstore_customer';
GRANT EXECUTE ON PROCEDURE Bookstore.SearchBooks TO 'bookstore_customer';
GRANT EXECUTE ON PROCEDURE Bookstore.PlaceOrder TO 'bookstore_customer';
GRANT EXECUTE ON PROCEDURE Bookstore.BorrowBook TO 'bookstore_customer';
GRANT EXECUTE ON PROCEDURE Bookstore.ReturnBook TO 'bookstore_customer';
GRANT EXECUTE ON PROCEDURE Bookstore.MarkOverdueLoans TO 'bookstore_customer';


GRANT 'bookstore_customer' TO 'bookstore_staff';
GRANT SELECT, INSERT, UPDATE ON Bookstore.Books TO 'bookstore_staff';
GRANT SELECT, INSERT, UPDATE ON Bookstore.Book_Copies TO 'bookstore_staff';
GRANT EXECUTE ON PROCEDURE Bookstore.AddBook TO 'bookstore_staff';
GRANT EXECUTE ON PROCEDURE Bookstore.RestockBook TO 'bookstore_staff';
GRANT EXECUTE ON PROCEDURE Bookstore.UpdateBook TO 'bookstore_staff';
GRANT EXECUTE ON PROCEDURE Bookstore.DeleteBook TO 'bookstore_staff';
GRANT EXECUTE ON PROCEDURE Bookstore.AddBookCopy TO 'bookstore_staff';
GRANT EXECUTE ON PROCEDURE Bookstore.LowStockReport TO 'bookstore_staff';

CREATE USER IF NOT EXISTS 'demo_customer'@'localhost' IDENTIFIED BY 'DemoCustomer#2026';
CREATE USER IF NOT EXISTS 'demo_staff'@'localhost' IDENTIFIED BY 'DemoStaff#2026';

GRANT 'bookstore_customer' TO 'demo_customer'@'localhost';
GRANT 'bookstore_staff' TO 'demo_staff'@'localhost';


SET DEFAULT ROLE 'bookstore_customer' TO 'demo_customer'@'localhost';
SET DEFAULT ROLE 'bookstore_staff' TO 'demo_staff'@'localhost';

SHOW GRANTS FOR 'bookstore_customer';
SHOW GRANTS FOR 'bookstore_staff';
SHOW GRANTS FOR 'demo_customer'@'localhost' USING 'bookstore_customer';
SHOW GRANTS FOR 'demo_staff'@'localhost' USING 'bookstore_staff';
