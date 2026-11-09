USE Bookstore;

DELIMITER $$

-- first procedure, in a case of searching for books
CREATE PROCEDURE SearchBooks(IN searchText VARCHAR(100))
BEGIN
    SELECT b.BookID, b.ISBN, b.Title,
           a.AuthorName, b.Price, b.Quantity
    FROM Books b
    JOIN Author a ON b.AuthorID = a.AuthorID
    WHERE LOWER(b.Title) LIKE CONCAT('%', LOWER(TRIM(searchText)), '%')
       OR LOWER(a.AuthorName) LIKE CONCAT('%', LOWER(TRIM(searchText)), '%');
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

DELIMITER ;
