import json
import logging
import time
from contextlib import contextmanager
from time import sleep
from typing import Any, Dict, List, Optional, Union

import psycopg2
import requests
from psycopg2 import sql
from psycopg2.extensions import cursor as Cursor, connection as Connection
from psycopg2.extras import RealDictCursor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import API_KEY, API_URL, BLACK_SEA_BBOX, RETRY_CONFIG, DB_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(module)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """Контекстный менеджер для подключения к БД с повторными попытками"""
    for attempt in range(RETRY_CONFIG['db']['max_retries']):
        conn = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = False
            logger.debug("Успешное подключение к БД")
            yield conn
            return
        except psycopg2.OperationalError as e:
            logger.warning(f"Ошибка подключения (попытка {attempt+1}): {str(e)}")
            if attempt < RETRY_CONFIG['db']['max_retries'] - 1:
                sleep(RETRY_CONFIG['db']['initial_delay'] * (2 ** attempt))
        finally:
            if conn:
                conn.close()
    raise RuntimeError("Не удалось подключиться к БД после нескольких попыток")

class FlightTracker:
    def __init__(self):
        self.session = self._configure_session()
    
    def _configure_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=RETRY_CONFIG['api']['max_retries'],
            backoff_factor=RETRY_CONFIG['api']['backoff_factor'],
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_flights(self) -> List[Dict[str, Any]]:
        try:
            response = self.session.get(
                API_URL,
                params={
                    "access_key": API_KEY,
                    "flight_status": "active",
                    "limit": 100
                },
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            if not isinstance(data.get('data'), list):
                logger.error("Некорректный формат ответа API")
                return []
            
            return data['data']
        
        except Exception as e:
            logger.error(f"Ошибка при получении данных: {str(e)}")
            return []

    def filter_flights(self, flights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered = []
        for flight in flights:
            try:
                live = flight.get('live') or {}
                lat = live.get('latitude')
                lon = live.get('longitude')

                if None in (lat, lon):
                    continue

                try:
                    lat_num = float(lat)
                    lon_num = float(lon)
                    if not (-90 <= lat_num <= 90) or not (-180 <= lon_num <= 180):
                        continue
                except (TypeError, ValueError):
                    continue

                if (BLACK_SEA_BBOX[0] <= lat_num <= BLACK_SEA_BBOX[2] and 
                    BLACK_SEA_BBOX[1] <= lon_num <= BLACK_SEA_BBOX[3]):
                    filtered.append(flight)
                    
            except Exception as e:
                logger.error(f"Ошибка фильтрации: {str(e)}", exc_info=True)
        
        return filtered

    def save_flights(self, flights: List[Dict[str, Any]]) -> None:
        logger.info(f"Начало сохранения {len(flights)} рейсов")
        success_count = 0
        failure_count = 0

        # Собираем уникальные aircrafts
        aircrafts = {}
        for flight in flights:
            aircraft_data = flight.get('aircraft', {})
            icao = aircraft_data.get('icao')
            if icao:
                model = aircraft_data.get('model', '').strip()
                aircrafts[icao] = model or icao

        if aircrafts:
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cursor:
                        insert_query = """
                            INSERT INTO aircrafts (icao_code, model_name)
                            VALUES (%s, %s)
                            ON CONFLICT (icao_code) DO UPDATE SET
                                model_name = CASE 
                                    WHEN EXCLUDED.model_name != EXCLUDED.icao_code 
                                    THEN EXCLUDED.model_name 
                                    ELSE aircrafts.model_name 
                                END
                        """
                        data = [(icao, model) for icao, model in aircrafts.items()]
                        cursor.executemany(insert_query, data)
                        conn.commit()
            except Exception as e:
                logger.error(f"Ошибка сохранения aircrafts: {str(e)}")

        # Сохраняем остальные данные
        for idx, flight in enumerate(flights):
            for attempt in range(RETRY_CONFIG['db']['max_retries']):
                try:
                    with get_db_connection() as conn:
                        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                            try:
                                if not all(key in flight for key in ('airline', 'flight', 'live')):
                                    raise ValueError("Некорректная структура данных рейса")

                                airline_data = flight['airline']
                                flight_data = flight['flight']
                                aircraft_data = flight.get('aircraft', {})
                                live_data = flight['live']

                                # Сохранение авиакомпании
                                cursor.execute(
                                    """INSERT INTO airlines (name, icao_code)
                                    VALUES (%(name)s, %(icao)s)
                                    ON CONFLICT (icao_code) DO UPDATE SET
                                        name = EXCLUDED.name
                                    RETURNING id""",
                                    {
                                        'name': airline_data.get('name', 'Unknown Airline'),
                                        'icao': airline_data['icao']
                                    }
                                )
                                airline_id = cursor.fetchone()['id']

                                # Сохранение рейса
                                cursor.execute(
                                    """INSERT INTO flights (
                                        flight_icao,
                                        aircraft_icao,
                                        airline_id,
                                        departure_airport,
                                        arrival_airport
                                    ) VALUES (
                                        %(flight_icao)s,
                                        %(aircraft_icao)s,
                                        %(airline_id)s,
                                        %(departure)s,
                                        %(arrival)s
                                    )
                                    ON CONFLICT (flight_icao, airline_id) DO UPDATE SET
                                        aircraft_icao = EXCLUDED.aircraft_icao,
                                        departure_airport = EXCLUDED.departure_airport,
                                        arrival_airport = EXCLUDED.arrival_airport,
                                        updated_at = NOW()
                                    RETURNING id""",
                                    {
                                        'flight_icao': flight_data['icao'],
                                        'aircraft_icao': aircraft_data.get('icao'),
                                        'airline_id': airline_id,
                                        'departure': flight.get('departure', {}).get('airport', 'N/A'),
                                        'arrival': flight.get('arrival', {}).get('airport', 'N/A')
                                    }
                                )
                                flight_id = cursor.fetchone()['id']

                                # Сохранение позиции
                                cursor.execute(
                                    """INSERT INTO flight_positions 
                                    (flight_id, latitude, longitude, altitude)
                                    VALUES (%s, %s, %s, %s)""",
                                    (
                                        flight_id,
                                        float(live_data['latitude']),
                                        float(live_data['longitude']),
                                        float(live_data.get('altitude', 0))
                                    )
                                )

                                conn.commit()
                                success_count += 1
                                break

                            except (KeyError, TypeError, ValueError) as e:
                                logger.error(f"Ошибка валидации данных рейса #{idx}: {str(e)}")
                                conn.rollback()
                                failure_count += 1
                                break

                            except psycopg2.Error as e:
                                logger.error(f"Ошибка БД (попытка {attempt+1}): {str(e)}")
                                conn.rollback()
                                if attempt == RETRY_CONFIG['db']['max_retries'] - 1:
                                    failure_count += 1
                                sleep(RETRY_CONFIG['db']['initial_delay'] * (2 ** attempt))

                except Exception as e:
                    logger.error(f"Критическая ошибка: {str(e)}")
                    failure_count += 1

        logger.info(f"Итог сохранения: Успешно {success_count}, Ошибок {failure_count}")

    def run(self):
        logger.info("Сервис мониторинга запущен")
        while True:
            try:
                flights = self.fetch_flights()
                if not flights:
                    logger.warning("Нет данных о рейсах")
                    sleep(60)
                    continue

                filtered = self.filter_flights(flights)
                if not filtered:
                    logger.info("Нет рейсов в зоне интереса")
                    sleep(300)
                    continue

                self.save_flights(filtered)
                sleep(3600)

            except KeyboardInterrupt:
                logger.info("Остановка по запросу пользователя")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
                sleep(60)

if __name__ == "__main__":
    tracker = FlightTracker()
    tracker.run()