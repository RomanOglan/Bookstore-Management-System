USE Bookstore;

INSERT INTO Author (AuthorID, AuthorName) VALUES
(101, 'George Orwell'),
(102, 'J.K. Rowling'),
(103, 'J.R.R. Tolkien'),
(104, 'Harper Lee'),
(105, 'Jane Austen');

INSERT INTO Category (CategoryID, CategoryName) VALUES
(101, 'Fiction'),
(102, 'Fantasy'),
(103, 'Classics'),
(104, 'Mystery'),
(105, 'Nonfiction');

-- All test users share the password: Password123!
INSERT INTO Users (UserID, Name, Email, PasswordHash, Role, AccountStatus) VALUES
(101, 'Ceedee Lamb', 'a.test@gmail.com', 'pbkdf2:sha256:1000000$Nl0gAbRM98SvrdWl$8ab10dd408446f070ad67300df6e1be9079ad9aa92c27c1cfe31c657a386ceaf', 'Customer', 'Active'),
(102, 'Jaxon Smith', 'b.test@gmail.com', 'pbkdf2:sha256:1000000$ohlqMiBkFonfBY4F$76f780bc180f5bad575b5f0efa05f4160c6310d8f60d11485fc749c4555704b9', 'Customer', 'Active'),
(103, 'John Stockton', 'c.test@gmail.com', 'pbkdf2:sha256:1000000$LKXMPEHQhY2q6Fwa$18b5d0e016bc1b3e74902b51649312c944f3ea4a5b01dfdee5963b0eb475296c', 'Customer', 'Active'),
(104, 'Bogdan Johnson', 'd.test@gmail.com', 'pbkdf2:sha256:1000000$oy9nCJJZXbo1JZ5L$746d6749a6ec86f1d2d5cc88b7c48805db92498046b9f9103f8f071bf43f3f3b', 'Staff', 'Active'),
(105, 'Daniel Green', 'e.test@gmail.com', 'pbkdf2:sha256:1000000$dL39ooj3r504fKys$d7b40c6f5ddab49b88367421c376371bfe369796d8ca8bd7a0cde2e9078b99e4', 'Customer', 'Inactive');

INSERT INTO Books (BookID, ISBN, Title, Rating, Description, Price, Quantity, AuthorID, CategoryID) VALUES
(101, '100001', '1984', 5, 'Dystopian fiction', 13.92, 8, 101, 101),
(102, '100002', 'Harry Potter and the Sorcerers Stone', 5, 'A young wizard begins his journey', 24.99, 6, 102, 102),
(103, '100003', 'The Hobbit', 5, 'A fantasy adventure', 20.21, 4, 103, 102),
(104, '100004', 'To Kill a Mockingbird', 4, 'A classic American novel', 12.63, 5, 104, 103),
(105, '100005', 'Pride and Prejudice', 4, 'A novel of manners and romance', 92.43, 3, 105, 103);

INSERT INTO Book_Copies (CopyID, Barcode, CopyStatus, BookID) VALUES
(101, 'COPY00000000101', 'Available', 101),
(102, 'COPY00000000102', 'On-Loan', 101),
(103, 'COPY00000000103', 'Available', 102),
(104, 'COPY00000000104', 'On-Loan', 103),
(105, 'COPY00000000105', 'Unavailable', 104),
(106, 'COPY00000000106', 'Available', 105);

INSERT INTO Orders (OrderID, OrderDate, DeliveryType, UserID) VALUES
(101, '2026-10-01 10:00:00', 'Delivery', 101),
(102, '2026-10-05 10:00:00', 'Pick-Up', 102),
(103, '2026-10-10 10:00:00', 'Delivery', 103),
(104, '2026-10-15 10:00:00', 'Pick-Up', 101);

INSERT INTO Order_Items (BookID, OrderID, Quantity, Price) VALUES
(101, 101, 1, 13.92),
(102, 101, 2, 24.99),
(103, 102, 1, 20.21),
(104, 103, 1, 12.63),
(105, 104, 2, 92.43);

INSERT INTO Loans (LoanID, UserID, CopyID, BorrowedDate, DueDate, ReturnedDate, LoanStatus) VALUES
(101, 101, 102, '2026-10-20', '2026-11-03', NULL, 'Late'),
(102, 102, 104, '2026-11-01', '2026-11-15', NULL, 'On-Loan'),
(103, 103, 101, '2026-09-01', '2026-09-15', '2026-09-12', 'Returned');

SELECT COUNT(*) AS Authors FROM Author;
SELECT COUNT(*) AS Categories FROM Category;
SELECT COUNT(*) AS Users FROM Users;
SELECT COUNT(*) AS Books FROM Books;
SELECT COUNT(*) AS BookCopies FROM Book_Copies;
SELECT COUNT(*) AS Orders FROM Orders;
SELECT COUNT(*) AS OrderItems FROM Order_Items;
SELECT COUNT(*) AS Loans FROM Loans;
