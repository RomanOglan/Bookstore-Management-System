USE Bookstore;

-- 1, Search books by title
SELECT BookID, ISBN, Title, Price, Quantity
FROM Books
WHERE Title LIKE '%Harry%';

-- 3, Search books by author
SELECT b.BookID, b.Title, a.AuthorName, b.Price, b.Quantity
FROM Books b
JOIN Author a ON b.AuthorID = a.AuthorID
WHERE a.AuthorName LIKE '%Rowling%';

-- 3, Search books by category
SELECT b.Title, c.CategoryName, b.Price, b.Quantity
FROM Books b
JOIN Category c ON b.CategoryID = c.CategoryID
WHERE c.CategoryName = 'Fantasy';

-- 4, Search books by ISBN
SELECT BookID, ISBN, Title, Price, Quantity
FROM Books
WHERE ISBN = 100002;

-- 5, Show available books
SELECT BookID, Title, Price, Quantity
FROM Books
WHERE Quantity > 0
ORDER BY Title;

-- 6, Show customer orders and totals
SELECT o.OrderID, o.OrderDate, o.DeliveryType,
       SUM(CAST(oi.Quantity AS UNSIGNED) * oi.Price) AS OrderTotal
FROM Orders o
JOIN Order_Items oi ON o.OrderID = oi.OrderID
WHERE o.UserID = 1
GROUP BY o.OrderID, o.OrderDate, o.DeliveryType
ORDER BY o.OrderDate DESC;

-- 7, Show books in an order
SELECT o.OrderID, b.Title, oi.Quantity,
       oi.Price AS PriceAtPurchase,
       CAST(oi.Quantity AS UNSIGNED) * oi.Price AS LineTotal
FROM Orders o
JOIN Order_Items oi ON o.OrderID = oi.OrderID
JOIN Books b ON oi.BookID = b.BookID
WHERE o.OrderID = 1;

-- 8, Show a customer's borrowed books
SELECT l.LoanID, b.Title, bc.Barcode,
       l.BorrowedDate, l.DueDate,
       l.ReturnedDate, l.LoanStatus
FROM Loans l
JOIN Book_Copies bc ON l.CopyID = bc.CopyID
JOIN Books b ON bc.BookID = b.BookID
WHERE l.UserID = 1
ORDER BY l.DueDate;

-- 9, Find books with low inventory
SELECT BookID, Title, Quantity
FROM Books
WHERE Quantity < 5
ORDER BY Quantity ASC;

-- 10, Show most purchased books
SELECT b.BookID, b.Title,
       SUM(CAST(oi.Quantity AS UNSIGNED)) AS UnitsSold
FROM Books b
JOIN Order_Items oi ON b.BookID = oi.BookID
GROUP BY b.BookID, b.Title
ORDER BY UnitsSold DESC;
