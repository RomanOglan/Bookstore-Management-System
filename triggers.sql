USE Bookstore;
DROP TRIGGER IF EXISTS ValidateOrderItem;
DROP TRIGGER IF EXISTS ValidateLoanDates;
DROP TRIGGER IF EXISTS BlockLoanReopen;
DROP TRIGGER IF EXISTS FreeCopyOnReturn;
DELIMITER $$

-- saftey measure, preventing invalid order quantities and prices
CREATE TRIGGER ValidateOrderItem
BEFORE INSERT ON Order_Items
FOR EACH ROW
BEGIN
    IF NEW.Quantity IS NULL OR NEW.Quantity = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid order quantity';
    END IF;

    IF NEW.Price IS NULL OR NEW.Price < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid order price';
    END IF;
END $$

-- a loan cannot be due before it was borrowed
CREATE TRIGGER ValidateLoanDates
BEFORE INSERT ON Loans
FOR EACH ROW
BEGIN
    IF NEW.DueDate < NEW.BorrowedDate THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Due date cannot be before the borrowed date';
    END IF;
END $$

-- a returned loan cannot be reopened
CREATE TRIGGER BlockLoanReopen
BEFORE UPDATE ON Loans
FOR EACH ROW
BEGIN
    IF OLD.LoanStatus = 'Returned' AND NEW.LoanStatus <> 'Returned' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'A returned loan cannot be reopened';
    END IF;
END $$

-- when a loan is returned, the copy becomes available again
CREATE TRIGGER FreeCopyOnReturn
AFTER UPDATE ON Loans
FOR EACH ROW
BEGIN
    IF OLD.LoanStatus <> 'Returned' AND NEW.LoanStatus = 'Returned' THEN
        UPDATE Book_Copies SET CopyStatus = 'Available' WHERE CopyID = NEW.CopyID;
    END IF;
END $$

DELIMITER ;
