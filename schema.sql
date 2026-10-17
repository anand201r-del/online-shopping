-- ===========================================
-- Online Shopping System — MySQL schema
-- Run once:   mysql -u root -p < schema.sql
-- Safe to re-run: it only creates what is missing.
-- ===========================================

CREATE DATABASE IF NOT EXISTS shopping_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE shopping_db;

-- 👤 Users (passwords are stored as werkzeug hashes)
CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)  NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 📦 Products  (column order matters: templates read id, name, price, stock, image, category)
CREATE TABLE IF NOT EXISTS products (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150)  NOT NULL,
    price       DECIMAL(10,2) NOT NULL DEFAULT 0,
    stock       INT           NOT NULL DEFAULT 0,
    image       VARCHAR(255)  NULL,
    category    VARCHAR(100)  NULL DEFAULT 'General'
);

-- 🛒 Cart
CREATE TABLE IF NOT EXISTS cart (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50) NOT NULL,
    product_id  INT         NOT NULL,
    quantity    INT         NOT NULL DEFAULT 1,
    UNIQUE KEY uq_cart (username, product_id)
);

-- ❤️ Wishlist
CREATE TABLE IF NOT EXISTS wishlist (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50) NOT NULL,
    product_id  INT         NOT NULL,
    UNIQUE KEY uq_wishlist (username, product_id)
);

-- 🧾 Orders (one row per product bought; name/price copied so history survives product edits)
CREATE TABLE IF NOT EXISTS orders (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)   NOT NULL,
    product_name  VARCHAR(150)  NOT NULL,
    price         DECIMAL(10,2) NOT NULL,
    quantity      INT           NOT NULL,
    total         DECIMAL(10,2) NOT NULL,
    order_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 🌱 Sample products (only added when the table is empty)
INSERT INTO products (name, price, stock, image, category)
SELECT * FROM (
    SELECT 'Wireless Headphones' AS name, 1999.00 AS price, 25 AS stock, 'headphones.jpg' AS image, 'Electronics' AS category
    UNION ALL SELECT 'Laptop',     54999.00, 10, 'laptop.jpg', 'Electronics'
    UNION ALL SELECT 'Smartphone', 15999.00, 15, 'phone.jpg',  'Electronics'
) AS seed
WHERE NOT EXISTS (SELECT 1 FROM products);
