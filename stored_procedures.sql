USE Bookstore;

DROP PROCEDURE IF EXISTS SearchBooks;
DROP PROCEDURE IF EXISTS PlaceOrder;
DROP PROCEDURE IF EXISTS BorrowBook;
DROP PROCEDURE IF EXISTS AddBook;
DROP PROCEDURE IF EXISTS RestockBook;
DROP PROCEDURE IF EXISTS UpdateBook;
DROP PROCEDURE IF EXISTS AddBookCopy;
DROP PROCEDURE IF EXISTS DeleteBook;
DROP PROCEDURE IF EXISTS LowStockReport;

DELIMITER $$

-- Procedure 1: catalog search by title, author, or ISBN, with an optional category filter and paging.
-- Ignores case and extra spaces. Words match in order, so "harry stone" finds "Harry Potter and the Stone".
-- Returns two result sets: first the total match count, then the requested page of books.
CREATE PROCEDURE SearchBooks(
    IN p_Search VARCHAR(100),
    IN p_CategoryID INT UNSIGNED,
    IN p_Limit INT,
    IN p_Offset INT
)
BEGIN
    DECLARE v_Term VARCHAR(100);
    DECLARE v_Pattern VARCHAR(120);
    DECLARE v_IsbnPart VARCHAR(100);

    SET v_Term = LOWER(TRIM(REGEXP_REPLACE(COALESCE(p_Search, ''), '[[:space:]]+', ' ')));
    SET v_Pattern = CONCAT('%', REPLACE(v_Term, ' ', '%'), '%');
    SET v_IsbnPart = REPLACE(REPLACE(v_Term, ' ', ''), '-', '');
    SET p_Limit = COALESCE(p_Limit, 24);
    SET p_Offset = COALESCE(p_Offset, 0);

    SELECT COUNT(*) AS total
      FROM Books b
      LEFT JOIN Author a ON b.AuthorID = a.AuthorID
     WHERE (v_Term = ''
            OR LOWER(b.Title) LIKE v_Pattern
            OR LOWER(COALESCE(a.AuthorName, '')) LIKE v_Pattern
            OR (v_IsbnPart <> '' AND b.ISBN LIKE CONCAT('%', v_IsbnPart, '%')))
       AND (p_CategoryID IS NULL OR b.CategoryID = p_CategoryID);

    SELECT b.BookID, b.ISBN, b.Title, b.Price, b.Quantity, b.CatalogStatus, b.Rating,
           a.AuthorName, c.CategoryName
      FROM Books b
      LEFT JOIN Author a ON b.AuthorID = a.AuthorID
      LEFT JOIN Category c ON b.CategoryID = c.CategoryID
     WHERE (v_Term = ''
            OR LOWER(b.Title) LIKE v_Pattern
            OR LOWER(COALESCE(a.AuthorName, '')) LIKE v_Pattern
            OR (v_IsbnPart <> '' AND b.ISBN LIKE CONCAT('%', v_IsbnPart, '%')))
       AND (p_CategoryID IS NULL OR b.CategoryID = p_CategoryID)
     ORDER BY b.Title
     LIMIT p_Limit OFFSET p_Offset;
END $$

-- for procedure 2, case in placing an order and update inventory
CREATE PROCEDURE PlaceOrder(
    IN p_UserID INT UNSIGNED,
    IN p_BookID INT UNSIGNED,
    IN p_Quantity INT,
    IN p_DeliveryType VARCHAR(20)
)
BEGIN
    DECLARE v_Price DECIMAL(19,4);
    DECLARE v_Stock INT;
    DECLARE v_OrderID INT UNSIGNED;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    IF p_Quantity IS NULL OR p_Quantity <= 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid quantity';
    END IF;

    IF p_DeliveryType IS NULL
       OR p_DeliveryType NOT IN ('Delivery', 'Pick-Up') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid delivery type';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM Users
        WHERE UserID = p_UserID AND AccountStatus = 'Active'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Active user not found';
    END IF;

    SELECT Price, Quantity
    INTO v_Price, v_Stock
    FROM Books
    WHERE BookID = p_BookID
    FOR UPDATE;

    IF v_Stock IS NULL OR v_Stock < p_Quantity THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Book unavailable or insufficient stock';
    END IF;

    INSERT INTO Orders (OrderDate, DeliveryType, UserID)
    VALUES (CURDATE(), p_DeliveryType, p_UserID);

    SET v_OrderID = LAST_INSERT_ID();

    INSERT INTO Order_Items (OrderID, BookID, Quantity, Price)
    VALUES (v_OrderID, p_BookID, p_Quantity, v_Price);

    UPDATE Books
    SET Quantity = Quantity - p_Quantity
    WHERE BookID = p_BookID;

    COMMIT;

    SELECT v_OrderID AS NewOrderID;
END $$

-- For procedure 3, case if borrowing an available book copy
CREATE PROCEDURE BorrowBook(
    IN p_UserID INT UNSIGNED,
    IN p_CopyID INT UNSIGNED
)
BEGIN
    DECLARE v_Status VARCHAR(20);
    DECLARE v_ActiveLoans INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    IF NOT EXISTS (
        SELECT 1 FROM Users
        WHERE UserID = p_UserID AND AccountStatus = 'Active'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Active user not found';
    END IF;

    SELECT COUNT(*) INTO v_ActiveLoans
    FROM Loans
    WHERE UserID = p_UserID AND LoanStatus IN ('On-Loan', 'Late');

    IF v_ActiveLoans >= 5 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Borrowing limit reached';
    END IF;

    SELECT CopyStatus INTO v_Status
    FROM Book_Copies
    WHERE CopyID = p_CopyID
    FOR UPDATE;

    IF v_Status IS NULL OR v_Status <> 'Available' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Book copy unavailable';
    END IF;

    INSERT INTO Loans
        (UserID, CopyID, BorrowedDate, DueDate, LoanStatus)
    VALUES
        (p_UserID, p_CopyID, CURDATE(),
         DATE_ADD(CURDATE(), INTERVAL 14 DAY), 'On-Loan');

    UPDATE Book_Copies
    SET CopyStatus = 'On-Loan'
    WHERE CopyID = p_CopyID;

    COMMIT;

    SELECT 'Book borrowed successfully' AS Result;
END $$

-- Procedure: staff adds a book. Validates the input, finds or creates the author, and inserts the
-- book in one transaction. Returns NewBookID.
CREATE PROCEDURE AddBook(
    IN p_Title VARCHAR(255),
    IN p_ISBN VARCHAR(13),
    IN p_Description VARCHAR(1000),
    IN p_Price DECIMAL(10,2),
    IN p_Quantity SMALLINT UNSIGNED,
    IN p_CategoryID INT UNSIGNED,
    IN p_AuthorName VARCHAR(100)
)
BEGIN
    DECLARE v_AuthorID INT UNSIGNED DEFAULT NULL;
    DECLARE v_BookID INT UNSIGNED;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_Title = TRIM(COALESCE(p_Title, ''));
    SET p_ISBN = NULLIF(TRIM(COALESCE(p_ISBN, '')), '');
    SET p_Description = NULLIF(TRIM(COALESCE(p_Description, '')), '');
    SET p_AuthorName = NULLIF(TRIM(COALESCE(p_AuthorName, '')), '');

    START TRANSACTION;

    IF p_Title = '' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Title is required';
    END IF;

    IF p_Price IS NULL OR p_Price < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Price cannot be negative';
    END IF;

    IF p_ISBN IS NOT NULL AND p_ISBN NOT REGEXP '^([0-9]{10}|[0-9]{13})$' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'ISBN must contain exactly 10 or 13 digits';
    END IF;

    IF p_ISBN IS NOT NULL AND EXISTS (SELECT 1 FROM Books WHERE ISBN = p_ISBN) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'A book with that ISBN already exists';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM Category WHERE CategoryID = p_CategoryID) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Choose a valid category';
    END IF;

    IF p_AuthorName IS NOT NULL THEN
        SELECT AuthorID INTO v_AuthorID
          FROM Author
         WHERE LOWER(AuthorName) = LOWER(p_AuthorName)
         LIMIT 1;

        IF v_AuthorID IS NULL THEN
            INSERT INTO Author (AuthorName) VALUES (p_AuthorName);
            SET v_AuthorID = LAST_INSERT_ID();
        END IF;
    END IF;

    INSERT INTO Books (Title, ISBN, Description, Price, Quantity, AuthorID, CategoryID)
    VALUES (p_Title, p_ISBN, p_Description, p_Price, p_Quantity, v_AuthorID, p_CategoryID);

    SET v_BookID = LAST_INSERT_ID();

    COMMIT;

    SELECT v_BookID AS NewBookID;
END $$

-- Procedure: staff adds stock to a book (a book with no quantity set counts as 0).
-- Returns the new quantity.
CREATE PROCEDURE RestockBook(
    IN p_BookID INT UNSIGNED,
    IN p_Amount INT
)
BEGIN
    DECLARE v_Exists INT DEFAULT 0;
    DECLARE v_Current INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    IF p_Amount IS NULL OR p_Amount < 1 OR p_Amount > 10000 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Restock amount must be between 1 and 10000';
    END IF;

    SELECT COUNT(*) INTO v_Exists
      FROM Books
     WHERE BookID = p_BookID
       FOR UPDATE;

    IF v_Exists = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Book not found';
    END IF;

    SELECT COALESCE(Quantity, 0) INTO v_Current
      FROM Books
     WHERE BookID = p_BookID;

    IF v_Current + p_Amount > 65535 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Stock cannot exceed 65535 copies';
    END IF;

    UPDATE Books
       SET Quantity = v_Current + p_Amount
     WHERE BookID = p_BookID;

    COMMIT;

    SELECT p_BookID AS BookID, v_Current + p_Amount AS NewQuantity;
END $$

-- Procedure: staff edits a book. Same rules as AddBook; a blank author clears the author.
CREATE PROCEDURE UpdateBook(
    IN p_BookID INT UNSIGNED,
    IN p_Title VARCHAR(255),
    IN p_ISBN VARCHAR(13),
    IN p_Description VARCHAR(1000),
    IN p_Price DECIMAL(10,2),
    IN p_Quantity SMALLINT UNSIGNED,
    IN p_CategoryID INT UNSIGNED,
    IN p_AuthorName VARCHAR(100)
)
BEGIN
    DECLARE v_AuthorID INT UNSIGNED DEFAULT NULL;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_Title = TRIM(COALESCE(p_Title, ''));
    SET p_ISBN = NULLIF(TRIM(COALESCE(p_ISBN, '')), '');
    SET p_Description = NULLIF(TRIM(COALESCE(p_Description, '')), '');
    SET p_AuthorName = NULLIF(TRIM(COALESCE(p_AuthorName, '')), '');

    START TRANSACTION;

    IF NOT EXISTS (SELECT 1 FROM Books WHERE BookID = p_BookID) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Book not found';
    END IF;

    IF p_Title = '' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Title is required';
    END IF;

    IF p_Price IS NULL OR p_Price < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Price cannot be negative';
    END IF;

    IF p_ISBN IS NOT NULL AND p_ISBN NOT REGEXP '^([0-9]{10}|[0-9]{13})$' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'ISBN must contain exactly 10 or 13 digits';
    END IF;

    IF p_ISBN IS NOT NULL AND EXISTS (SELECT 1 FROM Books WHERE ISBN = p_ISBN AND BookID <> p_BookID) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Another book already uses that ISBN';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM Category WHERE CategoryID = p_CategoryID) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Choose a valid category';
    END IF;

    IF p_AuthorName IS NOT NULL THEN
        SELECT AuthorID INTO v_AuthorID
          FROM Author
         WHERE LOWER(AuthorName) = LOWER(p_AuthorName)
         LIMIT 1;

        IF v_AuthorID IS NULL THEN
            INSERT INTO Author (AuthorName) VALUES (p_AuthorName);
            SET v_AuthorID = LAST_INSERT_ID();
        END IF;
    END IF;

    UPDATE Books
       SET Title = p_Title,
           ISBN = p_ISBN,
           Description = p_Description,
           Price = p_Price,
           Quantity = p_Quantity,
           AuthorID = v_AuthorID,
           CategoryID = p_CategoryID
     WHERE BookID = p_BookID;

    COMMIT;

    SELECT p_BookID AS BookID;
END $$

-- Procedure: staff adds a lendable copy (barcode) of a book.
CREATE PROCEDURE AddBookCopy(
    IN p_BookID INT UNSIGNED,
    IN p_Barcode VARCHAR(50)
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_Barcode = TRIM(COALESCE(p_Barcode, ''));

    START TRANSACTION;

    IF NOT EXISTS (SELECT 1 FROM Books WHERE BookID = p_BookID) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Book not found';
    END IF;

    IF p_Barcode = '' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Barcode is required';
    END IF;

    IF EXISTS (SELECT 1 FROM Book_Copies WHERE Barcode = p_Barcode) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'That barcode is already in use';
    END IF;

    INSERT INTO Book_Copies (Barcode, BookID) VALUES (p_Barcode, p_BookID);

    COMMIT;

    SELECT LAST_INSERT_ID() AS NewCopyID;
END $$

-- Procedure: staff deletes a book that has no copies and has never been ordered.
CREATE PROCEDURE DeleteBook(
    IN p_BookID INT UNSIGNED
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    IF NOT EXISTS (SELECT 1 FROM Books WHERE BookID = p_BookID) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Book not found';
    END IF;

    IF EXISTS (SELECT 1 FROM Order_Items WHERE BookID = p_BookID) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'This book appears in past orders and cannot be deleted';
    END IF;

    IF EXISTS (SELECT 1 FROM Book_Copies WHERE BookID = p_BookID) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'This book has lendable copies and cannot be deleted';
    END IF;

    DELETE FROM Books WHERE BookID = p_BookID;

    COMMIT;

    SELECT p_BookID AS DeletedBookID;
END $$

-- Procedure: books at or below a stock threshold (books with no quantity set are included),
-- optionally filtered by title, author or ISBN. Lowest stock first.
CREATE PROCEDURE LowStockReport(
    IN p_Threshold INT,
    IN p_Search VARCHAR(100)
)
BEGIN
    DECLARE v_Pattern VARCHAR(220);

    IF p_Threshold IS NULL OR p_Threshold < 0 THEN
        SET p_Threshold = 3;
    END IF;

    SET p_Search = TRIM(REGEXP_REPLACE(COALESCE(p_Search, ''), '[[:space:]]+', ' '));
    SET v_Pattern = CONCAT('%', REPLACE(p_Search, ' ', '%'), '%');

    SELECT b.BookID, b.Title, b.ISBN, b.Quantity, a.AuthorName, c.CategoryName
      FROM Books b
      LEFT JOIN Author a ON a.AuthorID = b.AuthorID
      LEFT JOIN Category c ON c.CategoryID = b.CategoryID
     WHERE (b.Quantity IS NULL OR b.Quantity <= p_Threshold)
       AND (p_Search = ''
            OR b.Title LIKE v_Pattern
            OR a.AuthorName LIKE v_Pattern
            OR b.ISBN LIKE v_Pattern)
     ORDER BY b.Quantity IS NULL, b.Quantity, b.Title;
END $$

DELIMITER ;
