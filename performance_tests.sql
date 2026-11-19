
SET @customer_email = 'customer@bookstore.local';
SET @customer_id = (SELECT UserID FROM Users WHERE Email = @customer_email);
SET @order_id = (SELECT MAX(OrderID) FROM Orders WHERE UserID = @customer_id);
SET @book_id = (SELECT MIN(BookID) FROM Books WHERE Quantity > 0);
SET @pattern = '%the%';

EXPLAIN
SELECT b.BookID, b.ISBN, b.Title, b.Price, b.Quantity, b.CatalogStatus, b.Rating,
       a.AuthorName, c.CategoryName
FROM Books b
LEFT JOIN Author a ON b.AuthorID = a.AuthorID
LEFT JOIN Category c ON b.CategoryID = c.CategoryID
WHERE (LOWER(b.Title) LIKE @pattern
       OR LOWER(COALESCE(a.AuthorName, '')) LIKE @pattern)
ORDER BY b.Title
LIMIT 24 OFFSET 0;

EXPLAIN ANALYZE
SELECT b.BookID, b.Title
FROM Books b
LEFT JOIN Author a ON b.AuthorID = a.AuthorID
WHERE (LOWER(b.Title) LIKE @pattern
       OR LOWER(COALESCE(a.AuthorName, '')) LIKE @pattern)
ORDER BY b.Title
LIMIT 24;


EXPLAIN
SELECT Price, Quantity FROM Books WHERE BookID = @book_id FOR UPDATE;


EXPLAIN
SELECT o.OrderID, o.OrderDate, o.DeliveryType,
       SUM(oi.Quantity * oi.Price) AS Total
FROM Orders o JOIN Order_Items oi ON o.OrderID = oi.OrderID
WHERE o.UserID = @customer_id
GROUP BY o.OrderID, o.OrderDate, o.DeliveryType
ORDER BY o.OrderDate DESC, o.OrderID DESC;


EXPLAIN
SELECT oi.BookID, b.Title, oi.Quantity, oi.Price,
       oi.Quantity * oi.Price AS LineTotal
FROM Order_Items oi JOIN Books b ON oi.BookID = b.BookID
WHERE oi.OrderID = @order_id
ORDER BY b.Title;


EXPLAIN
SELECT l.LoanID, u.Name, b.Title, l.DueDate,
       DATEDIFF(CURDATE(), l.DueDate) AS DaysOverdue
FROM Loans l
JOIN Users u ON l.UserID = u.UserID
JOIN Book_Copies bc ON l.CopyID = bc.CopyID
JOIN Books b ON bc.BookID = b.BookID
WHERE l.ReturnedDate IS NULL
  AND l.DueDate < CURDATE()
ORDER BY DaysOverdue DESC;
