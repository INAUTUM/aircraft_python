-- Создание таблицы авиакомпаний
CREATE TABLE IF NOT EXISTS airlines (
    id SERIAL PRIMARY KEY,
    icao_code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL
);

-- Создание таблицы самолетов
CREATE TABLE IF NOT EXISTS aircrafts (
    icao_code VARCHAR(10) PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    manufacturer VARCHAR(255)
);

-- Создание таблицы рейсов с составным уникальным индексом
CREATE TABLE IF NOT EXISTS flights (
    id SERIAL PRIMARY KEY,
    flight_icao VARCHAR(10) NOT NULL,
    aircraft_icao VARCHAR(10) REFERENCES aircrafts(icao_code),
    airline_id INTEGER NOT NULL REFERENCES airlines(id),
    departure_airport VARCHAR(255),
    arrival_airport VARCHAR(255),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_flight_airline UNIQUE (flight_icao, airline_id)
);

-- Оптимизация поиска по flight_icao и airline_id
CREATE INDEX IF NOT EXISTS flights_search_idx 
ON flights (flight_icao, airline_id);

-- Создание таблицы позиций рейсов
CREATE TABLE IF NOT EXISTS flight_positions (
    id SERIAL PRIMARY KEY,
    flight_id INTEGER REFERENCES flights(id),
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    altitude FLOAT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Создание материализованного представления
CREATE MATERIALIZED VIEW IF NOT EXISTS flight_counts AS
SELECT
    a.model_name,
    al.name AS airline_name,
    DATE_TRUNC('hour', f.updated_at) AS hour,
    COUNT(*) AS flight_count
FROM
    flights f
JOIN aircrafts a ON f.aircraft_icao = a.icao_code
JOIN airlines al ON f.airline_id = al.id
GROUP BY
    a.model_name,
    al.name,
    DATE_TRUNC('hour', f.updated_at);

-- Создание уникального индекса для материализованного представления
CREATE UNIQUE INDEX IF NOT EXISTS flight_counts_idx 
ON flight_counts (model_name, airline_name, hour);

-- Индекс для ускорения поиска по ICAO коду
CREATE INDEX IF NOT EXISTS aircrafts_icao_idx 
ON aircrafts (icao_code);

INSERT INTO aircrafts (icao_code, model_name)
VALUES ('UNKNOWN', 'UNKNOWN')
ON CONFLICT DO NOTHING;