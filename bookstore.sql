CREATE DATABASE IF NOT EXISTS Bookstore;
USE Bookstore;


CREATE TABLE IF NOT EXISTS Author (
    AuthorID INT UNSIGNED AUTO_INCREMENT,
    AuthorName VARCHAR(50), 
    PRIMARY KEY (AuthorID)
);

CREATE TABLE IF NOT EXISTS Category (
    CategoryID INT UNSIGNED AUTO_INCREMENT,
    CategoryName VARCHAR(20),
    PRIMARY KEY (CategoryID)
);

CREATE TABLE IF NOT EXISTS Books (
    BookID INT UNSIGNED AUTO_INCREMENT,
    ISBN INT UNIQUE,
    Title VARCHAR(50),
    Rating INT, --Adding rating cause its in our dataset so why not--
    Description VARCHAR(50),
    Price DECIMAL(19, 4),
    Quantity SMALLINT UNSIGNED,
    AuthorID INT UNSIGNED,
    CategoryID INT UNSIGNED,
    PRIMARY KEY(BookID),
    FOREIGN KEY (AuthorID) REFERENCES Author (AuthorID),
    FOREIGN KEY (CategoryID) REFERENCES Category (CategoryID)
);

CREATE TABLE IF NOT EXISTS Book_Copies (
    CopyID INT UNSIGNED AUTO_INCREMENT,
    Barcode CHAR(15) UNIQUE, -- Double check with group how we want to do BarCode--
    CopyStatus ENUM ("Available", "On-Loan", "Unavailable"), -- Review these options--
    BookID INT UNSIGNED,
    PRIMARY KEY(CopyID),
    FOREIGN KEY (BookID) REFERENCES Books (BookID)
);

CREATE TABLE IF NOT EXISTS Loans (
    LoanID INT UNSIGNED AUTO_INCREMENT,
    UserID INT UNSIGNED,
    BorrowedDate DATE,
    DueDate DATE,
    ReturnedDate DATE,
    -- Removing OverDue fee from table, we will calculate it in the backend using borroed Date and Returned Date (or lack thereof)
    LoanStatus ENUM ("On-Loan", "Returned", "Late", "Available for Loan"),
    CopyID INT UNSIGNED,
    PRIMARY KEY(LoanID),
    FOREIGN KEY(UserID) REFERENCES Users(UserID),
    FOREIGN KEY(CopyID) REFERENCES Book_Copies(CopyID)
    -- Removed BookID from Loans as we can grab it from Book_Copies using CopyID
);

CREATE TABLE IF NOT EXISTS Users (
    UserID INT UNSIGNED AUTO_INCREMENT,
    Name VARCHAR(100),
    Email VARCHAR(50) UNIQUE NOT NULL,
    PasswordHash VARCHAR(250) NOT NULL,
    Role ENUM ("Admin", "Users") NOT NULL,
    AccountStatus ENUM ("Active", "Unactive") DEFAULT("Active") NOT NULL,
    PRIMARY KEY(UserID)
);

CREATE TABLE IF NOT EXISTS Order_Items (
    BookID INT UNSIGNED,
    OrderID INT UNSIGNED,
    Quantity VARCHAR(20),
    Price DECIMAL(19, 4),
    PRIMARY KEY(BookID, OrderID),
    FOREIGN KEY(BookID) REFERENCES Books(BookID),
    FOREIGN KEY(OrderID) REFERENCES Orders (OrderID)
);

CREATE TABLE IF NOT EXISTS Orders (
    OrderID INT UNSIGNED AUTO_INCREMENT,
    OrderDate DATE,
    DeliveryType ENUM ("Delivery", "Pick-Up"),
    UserID INT UNSIGNED,
    PRIMARY KEY (OrderID),
    FOREIGN KEY (UserID) REFERENCES Users (UserID)
);


SHOW TABLEs;