-- Enable foreign keys (PostgreSQL always has this ON)
-- No PRAGMA needed in PostgreSQL

-- ADMIN TABLE
CREATE TABLE IF NOT EXISTS admin (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

-- CATEGORY TABLE
CREATE TABLE IF NOT EXISTS category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DESIGN TABLE
CREATE TABLE IF NOT EXISTS design (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    image_url TEXT NOT NULL,
    category_id INTEGER,
    featured INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE SET NULL
);

-- Optional starter categories
INSERT INTO category (name)
    VALUES ('Logo'), ('Banner'), ('Social Post')
ON CONFLICT DO NOTHING;
