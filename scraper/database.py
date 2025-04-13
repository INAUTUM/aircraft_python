import psycopg2 # type: ignore
from psycopg2.extras import RealDictCursor # type: ignore
from contextlib import contextmanager
from config import DB_CONFIG, RETRY_CONFIG, LOGGING_CONFIG
from typing import Optional, Union, List, Dict
from psycopg2.extensions import cursor as Cursor, connection as Connection  # type: ignore
import logging
import time
import logging.config

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """Контекстный менеджер для подключения к БД с повторными попытками"""
    for attempt in range(RETRY_CONFIG['db']['max_retries']):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            logger.info("Успешное подключение к БД")
            yield conn
            return
        except psycopg2.OperationalError as e:
            logger.warning(f"Ошибка подключения (попытка {attempt+1}): {str(e)}")
            if attempt < RETRY_CONFIG['db']['max_retries'] - 1:
                time.sleep(RETRY_CONFIG['db']['initial_delay'] * (2 ** attempt))  # Используем time.sleep
        finally:
            if 'conn' in locals():
                conn.close()
    raise RuntimeError("Не удалось подключиться к БД после нескольких попыток")

@contextmanager
def get_db_cursor():
    """Контекстный менеджер для работы с курсором"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction rolled back: {str(e)}")
                raise
            finally:
                cursor.close()
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

def execute_query(
    query: str,
    params: Optional[Union[dict, tuple, list]] = None,
    cursor: Optional[Cursor] = None,
    return_result: bool = True
) -> Optional[Union[List[Dict], int]]:
    """
    Универсальная функция выполнения SQL-запросов с улучшенным управлением транзакциями
    
    Параметры:
        query: SQL-запрос
        params: Параметры запроса
        cursor: Существующий курсор (опционально)
        return_result: Возвращать ли результат (по умолчанию True)
    
    Возвращает:
        - Для SELECT: список словарей с результатами
        - Для INSERT/UPDATE/DELETE с RETURNING: список словарей
        - Для других DML: количество затронутых строк
        - None в случае ошибки
    """
    conn = None
    own_cursor = False
    result = None
    
    try:
        # Логирование параметров
        logger.debug(f"Executing query: {query}")
        logger.debug(f"Params: {params}")

        # Работа с существующим курсором
        if cursor:
            cursor.execute(query, params)
            if return_result and cursor.description:
                columns = [desc[0] for desc in cursor.description]
                result = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return result

        # Создание нового соединения
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor(cursor_factory=RealDictCursor) as new_cursor:
            new_cursor.execute(query, params)
            
            # Обработка результатов
            if return_result:
                if new_cursor.description:
                    result = new_cursor.fetchall()
                else:
                    result = new_cursor.rowcount
            
            conn.commit()
            return result

    except psycopg2.Error as e:
        logger.error(f"Database error: {str(e)}")
        if conn:
            conn.rollback()
        raise  # Пробрасываем исключение для обработки на верхнем уровне
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if conn and not cursor:  # Закрываем только собственные соединения
            conn.close()

def log_to_db(message: str, level: str = 'INFO'):
    with get_db_cursor() as cursor:
        cursor.execute(
            """INSERT INTO logs (message, level, timestamp)
            VALUES (%s, %s, NOW())""",
            (message, level)
        )