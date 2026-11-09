# Bookstore-Management-System

### How to Run
Using MySQL;
1. Install MySQL Server and MySQL Workbench.
2. Open MySQL Workbench and connect to your local MySQL server.
3. Open and execute `bookstore.sql` to create the database and tables.
4. Open and execute `test_data.sql` to populate the database with sample data.
5. Execute `backend_queries.sql` to run the 10 SQL queries.
6. Execute `stored_procedures.sql` to create the three stored procedures.
7. Execute `triggers.sql` to create the validation trigger.

Run these commands in a new SQL tab to test:
sql
USE Bookstore;
CALL SearchBooks('Harry');
CALL PlaceOrder(101, 102, 1, 'Delivery');
CALL BorrowBook(101, 101);


Using Web;
1. Visitdb-fiddle.com
2. Select MySQL 8.0.
3. Paste bookstore.sql into Schema SQL.
4. Below it, paste test_data.sql, stored_procedures.sql, and triggers.sql, in that order.
5. Paste backend_queries.sql into Query SQL.

Click Run to view the results.


