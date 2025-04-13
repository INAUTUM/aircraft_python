-- Основное обновление известных моделей
INSERT INTO aircrafts (icao_code, model_name)
VALUES
    ('A20N', 'Airbus A320neo'),
    ('A333', 'Airbus A330-300'),
    ('B763', 'Boeing 767-300'),
    ('A320', 'Airbus A320'),
    ('E170', 'Embraer 170'),
    ('A321', 'Airbus A321'),
    ('AT76', 'ATR 72-600'),
    ('DHC6', 'De Havilland Canada DHC-6 Twin Otter'),
    ('B38M', 'Boeing 737 MAX 8'),
    ('B78X', 'Boeing 787-10 Dreamliner'),
    ('B734', 'Boeing 737-400'),
    ('C208', 'Cessna 208 Caravan'),
    ('PC12', 'Pilatus PC-12'),
    ('BE20', 'Beechcraft King Air 200'),
    ('A21N', 'Airbus A321neo'),
    ('B788', 'Boeing 787-8 Dreamliner'),
    ('B738', 'Boeing 737-800')
ON CONFLICT (icao_code) DO UPDATE SET
    model_name = EXCLUDED.model_name;

-- Обновление для записей с Unknown Model
WITH excluded_codes AS (
    SELECT UNNEST(ARRAY[
        'A20N', 'A333', 'B763', 'A320', 'E170',
        'A321', 'AT76', 'DHC6', 'B38M', 'B78X',
        'B734', 'C208', 'PC12', 'BE20', 'A21N',
        'B788', 'B738'
    ]) AS code
)
UPDATE aircrafts 
SET model_name = icao_code 
WHERE model_name = 'Unknown Model'
    AND icao_code NOT IN (SELECT code FROM excluded_codes);

-- Добавление специальных случаев
INSERT INTO aircrafts (icao_code, model_name)
VALUES
    ('JS32', 'British Aerospace Jetstream 32'),
    ('SU95', 'Sukhoi Superjet 100-95')
ON CONFLICT (icao_code) DO UPDATE SET
    model_name = EXCLUDED.model_name;