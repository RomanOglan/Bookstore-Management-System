USE Bookstore;

-- Backend reporting queries, written for the real data:
-- about 1,000 books imported from bookstore.csv (no authors or ISBNs),
-- CSV genres as categories, demo stock of 3-17 per book,
-- and orders/loans placed through the website.
-- Users are looked up by email, never by a hard-coded ID.

-- Settings (change these, not the queries).
-- @late_fee_per_day must match the fee rate chosen for the loans pages.
SET @customer_email = 'customer@bookstore.local';
SET @low_stock_threshold = 5;
SET @late_fee_per_day = 0.25;


-- 1, Overdue loans: due date passed and not returned, with the late fee so far
SELECT l.LoanID, u.Name, u.Email, b.Title, bc.Barcode,
       l.BorrowedDate, l.DueDate,
       DATEDIFF(CURDATE(), l.DueDate) AS DaysOverdue,
       ROUND(DATEDIFF(CURDATE(), l.DueDate) * @late_fee_per_day, 2) AS LateFee
FROM Loans l
JOIN Users u ON l.UserID = u.UserID
JOIN Book_Copies bc ON l.CopyID = bc.CopyID
JOIN Books b ON bc.BookID = b.BookID
WHERE l.ReturnedDate IS NULL
  AND l.DueDate < CURDATE()
ORDER BY DaysOverdue DESC;


-- 2, Low stock: books for sale with @low_stock_threshold copies or fewer
SELECT b.BookID, b.Title, c.CategoryName, b.Quantity, b.Price
FROM Books b
LEFT JOIN Category c ON b.CategoryID = c.CategoryID
WHERE b.Quantity IS NOT NULL
  AND b.Quantity <= @low_stock_threshold
ORDER BY b.Quantity ASC, b.Title;


-- 3, Sales by category: revenue uses the price at purchase (Order_Items.Price)
SELECT c.CategoryName,
       COUNT(DISTINCT oi.OrderID) AS Orders,
       SUM(oi.Quantity) AS UnitsSold,
       SUM(oi.Quantity * oi.Price) AS Revenue
FROM Order_Items oi
JOIN Books b ON oi.BookID = b.BookID
JOIN Category c ON b.CategoryID = c.CategoryID
GROUP BY c.CategoryID, c.CategoryName
ORDER BY Revenue DESC;


-- 4, Top sellers: the 10 books with the most units sold
SELECT b.BookID, b.Title, c.CategoryName,
       SUM(oi.Quantity) AS UnitsSold,
       SUM(oi.Quantity * oi.Price) AS Revenue,
       b.Quantity AS InStock
FROM Order_Items oi
JOIN Books b ON oi.BookID = b.BookID
LEFT JOIN Category c ON b.CategoryID = c.CategoryID
GROUP BY b.BookID, b.Title, c.CategoryName, b.Quantity
ORDER BY UnitsSold DESC, Revenue DESC
LIMIT 10;


-- 5, One customer's order history, looked up by email
SELECT o.OrderID, o.OrderDate, o.DeliveryType,
       SUM(oi.Quantity) AS Items,
       SUM(oi.Quantity * oi.Price) AS OrderTotal
FROM Users u
JOIN Orders o ON o.UserID = u.UserID
JOIN Order_Items oi ON oi.OrderID = o.OrderID
WHERE u.Email = @customer_email
GROUP BY o.OrderID, o.OrderDate, o.DeliveryType
ORDER BY o.OrderDate DESC;
