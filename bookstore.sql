-- Non-destructive schema setup for MySQL 8.0.
-- Existing rows are preserved. Use setup_database.py --reset only for an intentional rebuild.
CREATE DATABASE IF NOT EXISTS Bookstore
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE Bookstore;

CREATE TABLE IF NOT EXISTS Users (
    UserID        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    Name          VARCHAR(100) NOT NULL,
    Email         VARCHAR(255) NOT NULL UNIQUE,
    PasswordHash  VARCHAR(255) NOT NULL,
    Role          ENUM('Customer', 'Staff') NOT NULL DEFAULT 'Customer',
    AccountStatus ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS Author (
    AuthorID   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    AuthorName VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Category (
    CategoryID   INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    CategoryName VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS Books (
    BookID        INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ISBN          VARCHAR(13) UNIQUE,
    Title         VARCHAR(255) NOT NULL,
    Rating        TINYINT UNSIGNED,
    Description   VARCHAR(1000),
    Price         DECIMAL(10, 2) NOT NULL,
    Quantity      SMALLINT UNSIGNED NULL,
    CatalogStatus VARCHAR(50),
    SourceURL     VARCHAR(500) UNIQUE,
    AuthorID      INT UNSIGNED,
    CategoryID    INT UNSIGNED,
    CONSTRAINT fk_books_author FOREIGN KEY (AuthorID) REFERENCES Author (AuthorID),
    CONSTRAINT fk_books_category FOREIGN KEY (CategoryID) REFERENCES Category (CategoryID),
    CONSTRAINT chk_books_rating CHECK (Rating IS NULL OR Rating BETWEEN 1 AND 5),
    CONSTRAINT chk_books_price CHECK (Price >= 0),
    INDEX idx_books_title (Title),
    INDEX idx_books_isbn (ISBN)
);

CREATE TABLE IF NOT EXISTS Book_Copies (
    CopyID     INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    Barcode    VARCHAR(50) NOT NULL UNIQUE,
    CopyStatus ENUM('Available', 'On-Loan', 'Unavailable') NOT NULL DEFAULT 'Available',
    BookID     INT UNSIGNED NOT NULL,
    CONSTRAINT fk_copies_book FOREIGN KEY (BookID) REFERENCES Books (BookID)
);

CREATE TABLE IF NOT EXISTS Loans (
    LoanID       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    UserID       INT UNSIGNED NOT NULL,
    CopyID       INT UNSIGNED NOT NULL,
    BorrowedDate DATE NOT NULL,
    DueDate      DATE NOT NULL,
    ReturnedDate DATE,
    LoanStatus   ENUM('On-Loan', 'Returned', 'Late') NOT NULL DEFAULT 'On-Loan',
    LateFee      DECIMAL(8,2) NOT NULL DEFAULT 0,
    CONSTRAINT fk_loans_user FOREIGN KEY (UserID) REFERENCES Users (UserID),
    CONSTRAINT fk_loans_copy FOREIGN KEY (CopyID) REFERENCES Book_Copies (CopyID),
    INDEX idx_loans_due (DueDate, ReturnedDate)
);

CREATE TABLE IF NOT EXISTS Orders (
    OrderID      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    OrderDate    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    DeliveryType ENUM('Delivery', 'Pick-Up') NOT NULL,
    UserID       INT UNSIGNED NOT NULL,
    CONSTRAINT fk_orders_user FOREIGN KEY (UserID) REFERENCES Users (UserID)
);

CREATE TABLE IF NOT EXISTS Order_Items (
    BookID   INT UNSIGNED NOT NULL,
    OrderID  INT UNSIGNED NOT NULL,
    Quantity SMALLINT UNSIGNED NOT NULL,
    Price    DECIMAL(10, 2) NOT NULL,
    PRIMARY KEY (BookID, OrderID),
    CONSTRAINT fk_items_book FOREIGN KEY (BookID) REFERENCES Books (BookID),
    CONSTRAINT fk_items_order FOREIGN KEY (OrderID) REFERENCES Orders (OrderID),
    CONSTRAINT chk_items_quantity CHECK (Quantity > 0),
    CONSTRAINT chk_items_price CHECK (Price >= 0)
);
