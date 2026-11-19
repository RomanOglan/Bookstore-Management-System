-- Bookstore schema. Load order: this file, test_data.sql, stored_procedures.sql, triggers.sql
DROP DATABASE IF EXISTS Bookstore;
CREATE DATABASE Bookstore;
USE Bookstore;

CREATE TABLE Users (
    UserID        INT UNSIGNED AUTO_INCREMENT,
    Name          VARCHAR(100) NOT NULL,
    Email         VARCHAR(255) NOT NULL UNIQUE,
    PasswordHash  VARCHAR(255) NOT NULL,
    Role          ENUM('Customer', 'Staff') NOT NULL,
    AccountStatus ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active',
    PRIMARY KEY (UserID)
);

CREATE TABLE Author (
    AuthorID   INT UNSIGNED AUTO_INCREMENT,
    AuthorName VARCHAR(100) NOT NULL,
    PRIMARY KEY (AuthorID)
);

CREATE TABLE Category (
    CategoryID   INT UNSIGNED AUTO_INCREMENT,
    CategoryName VARCHAR(50) NOT NULL UNIQUE,
    PRIMARY KEY (CategoryID)
);

CREATE TABLE Books (
    BookID      INT UNSIGNED AUTO_INCREMENT,
    ISBN        VARCHAR(13) UNIQUE,
    Title       VARCHAR(255) NOT NULL,
    Rating      TINYINT UNSIGNED,
    Description VARCHAR(500),
    Price       DECIMAL(19, 4) NOT NULL,
    Quantity    SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    AuthorID    INT UNSIGNED,
    CategoryID  INT UNSIGNED,
    PRIMARY KEY (BookID),
    FOREIGN KEY (AuthorID)   REFERENCES Author (AuthorID),
    FOREIGN KEY (CategoryID) REFERENCES Category (CategoryID),
    CHECK (Rating IS NULL OR Rating BETWEEN 0 AND 5),
    INDEX idx_books_title (Title),
    FULLTEXT INDEX ft_books_search (Title, Description)
);

CREATE TABLE Book_Copies (
    CopyID     INT UNSIGNED AUTO_INCREMENT,
    Barcode    CHAR(15) NOT NULL UNIQUE,
    CopyStatus ENUM('Available', 'On-Loan', 'Unavailable') NOT NULL DEFAULT 'Available',
    BookID     INT UNSIGNED NOT NULL,
    PRIMARY KEY (CopyID),
    FOREIGN KEY (BookID) REFERENCES Books (BookID)
);

CREATE TABLE Loans (
    LoanID       INT UNSIGNED AUTO_INCREMENT,
    UserID       INT UNSIGNED NOT NULL,
    CopyID       INT UNSIGNED NOT NULL,
    BorrowedDate DATE NOT NULL,
    DueDate      DATE NOT NULL,
    ReturnedDate DATE,
    LoanStatus   ENUM('On-Loan', 'Returned', 'Late') NOT NULL DEFAULT 'On-Loan',
    PRIMARY KEY (LoanID),
    FOREIGN KEY (UserID) REFERENCES Users (UserID),
    FOREIGN KEY (CopyID) REFERENCES Book_Copies (CopyID),
    INDEX idx_loans_due (DueDate, ReturnedDate)
);

CREATE TABLE Orders (
    OrderID      INT UNSIGNED AUTO_INCREMENT,
    OrderDate    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    DeliveryType ENUM('Delivery', 'Pick-Up') NOT NULL,
    UserID       INT UNSIGNED NOT NULL,
    PRIMARY KEY (OrderID),
    FOREIGN KEY (UserID) REFERENCES Users (UserID)
);

CREATE TABLE Order_Items (
    BookID   INT UNSIGNED NOT NULL,
    OrderID  INT UNSIGNED NOT NULL,
    Quantity SMALLINT UNSIGNED NOT NULL,
    Price    DECIMAL(19, 4) NOT NULL,
    PRIMARY KEY (BookID, OrderID),
    FOREIGN KEY (BookID)  REFERENCES Books (BookID),
    FOREIGN KEY (OrderID) REFERENCES Orders (OrderID),
    CHECK (Quantity > 0)
);

SHOW TABLES;
