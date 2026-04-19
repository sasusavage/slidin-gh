-- Slidein GH — PostgreSQL Schema
-- Run: psql -U postgres -d slidin_store -f schema.sql
-- Or use: flask db upgrade (after flask db init / flask db migrate)

CREATE DATABASE slidin_store;
\c slidin_store;

-- Drop order matters
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS product_variants CASCADE;
DROP TABLE IF EXISTS product_images CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS admin_users CASCADE;

CREATE TABLE categories (
    id          VARCHAR(36) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    slug        VARCHAR(120) UNIQUE NOT NULL,
    description TEXT,
    image_url   VARCHAR(500),
    position    INTEGER DEFAULT 0,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE products (
    id               VARCHAR(36) PRIMARY KEY,
    name             VARCHAR(200) NOT NULL,
    slug             VARCHAR(220) UNIQUE NOT NULL,
    description      TEXT,
    price            NUMERIC(10,2) NOT NULL,
    compare_at_price NUMERIC(10,2),
    category_id      VARCHAR(36) REFERENCES categories(id),
    status           VARCHAR(20) DEFAULT 'active',
    featured         BOOLEAN DEFAULT FALSE,
    gender           VARCHAR(20),
    brand            VARCHAR(100),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE product_images (
    id          VARCHAR(36) PRIMARY KEY,
    product_id  VARCHAR(36) NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    url         VARCHAR(500) NOT NULL,
    alt_text    VARCHAR(200),
    position    INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE product_variants (
    id          VARCHAR(36) PRIMARY KEY,
    product_id  VARCHAR(36) NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    size        VARCHAR(20),
    color       VARCHAR(50),
    color_hex   VARCHAR(10),
    sku         VARCHAR(100),
    price       NUMERIC(10,2),
    quantity    INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE customers (
    id            VARCHAR(36) PRIMARY KEY,
    full_name     VARCHAR(200) NOT NULL,
    email         VARCHAR(200),
    phone         VARCHAR(30) NOT NULL,
    address_line1 VARCHAR(300),
    address_line2 VARCHAR(300),
    city          VARCHAR(100),
    region        VARCHAR(100),
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE orders (
    id               VARCHAR(36) PRIMARY KEY,
    order_number     VARCHAR(20) UNIQUE NOT NULL,
    customer_id      VARCHAR(36) REFERENCES customers(id),
    delivery_name    VARCHAR(200) NOT NULL,
    delivery_phone   VARCHAR(30) NOT NULL,
    delivery_email   VARCHAR(200),
    delivery_address VARCHAR(500) NOT NULL,
    delivery_city    VARCHAR(100) NOT NULL,
    delivery_region  VARCHAR(100),
    delivery_notes   TEXT,
    subtotal         NUMERIC(10,2) NOT NULL,
    delivery_fee     NUMERIC(10,2) DEFAULT 0,
    total            NUMERIC(10,2) NOT NULL,
    status           VARCHAR(30) DEFAULT 'pending',
    payment_method   VARCHAR(50) DEFAULT 'cash_on_delivery',
    payment_status   VARCHAR(30) DEFAULT 'pending',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_items (
    id            VARCHAR(36) PRIMARY KEY,
    order_id      VARCHAR(36) NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id    VARCHAR(36) REFERENCES products(id),
    variant_id    VARCHAR(36) REFERENCES product_variants(id),
    product_name  VARCHAR(200) NOT NULL,
    product_image VARCHAR(500),
    size          VARCHAR(20),
    color         VARCHAR(50),
    price         NUMERIC(10,2) NOT NULL,
    quantity      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE admin_users (
    id            VARCHAR(36) PRIMARY KEY,
    username      VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_products_status   ON products(status);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_featured ON products(featured);
CREATE INDEX idx_variants_product  ON product_variants(product_id);
CREATE INDEX idx_images_product    ON product_images(product_id);
CREATE INDEX idx_orders_customer   ON orders(customer_id);
CREATE INDEX idx_orders_number     ON orders(order_number);
CREATE INDEX idx_orders_status     ON orders(status);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_customers_phone   ON customers(phone);

-- Sample seed data
INSERT INTO categories (id, name, slug, position, is_active) VALUES
  ('cat-1', 'Sneakers', 'sneakers', 1, TRUE),
  ('cat-2', 'Slides & Crocs', 'slides-crocs', 2, TRUE),
  ('cat-3', 'Bags', 'bags', 3, TRUE),
  ('cat-4', 'Apparel', 'apparel', 4, TRUE);