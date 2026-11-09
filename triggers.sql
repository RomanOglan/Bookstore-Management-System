USE Bookstore;
DELIMITER $$

-- saftey measure, preventing invalid order quantities and prices
CREATE TRIGGER ValidateOrderItem
BEFORE INSERT ON Order_Items
FOR EACH ROW
BEGIN
    IF NEW.Quantity IS NULL
       OR NEW.Quantity NOT REGEXP '^[0-9]+$'
       OR CAST(NEW.Quantity AS UNSIGNED) = 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid order quantity';
    END IF;

    IF NEW.Price IS NULL OR NEW.Price < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid order price';
    END IF;
END $$

DELIMITER ;