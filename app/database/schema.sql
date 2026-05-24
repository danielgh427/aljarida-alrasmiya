-- MySQL Schema: Lebanese Laws & Tenders RAG Chatbot
-- Generated: 2026-05-24

CREATE TABLE IF NOT EXISTS laws (
    id INT AUTO_INCREMENT PRIMARY KEY,
    link VARCHAR(500) UNIQUE,
    title TEXT,
    law_type TEXT,
    law_number VARCHAR(50),
    law_date VARCHAR(50),
    content LONGTEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tenders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    link VARCHAR(500) UNIQUE,
    title TEXT,
    summary TEXT,
    final_submission_deadline DATETIME,
    opening_session_date DATETIME,
    document_price DECIMAL(15,2),
    document_location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
