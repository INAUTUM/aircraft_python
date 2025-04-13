import os

# Конфигурация API
API_KEY = os.getenv("API_KEY")  # Берем из переменных окружения
API_URL = "http://api.aviationstack.com/v1/flights"

# BLACK_SEA_BBOX = (41.0, 27.5, 44.5, 41.5) 
BLACK_SEA_BBOX = (-90, -180, 90, 180)  # Весь мир

RETRY_CONFIG = {
    'api': {
        'max_retries': 5,
        'backoff_factor': 1
    },
    'db': {
        'max_retries': 3,
        'initial_delay': 1
    }
}

DB_CONFIG = {
    "dbname": "aviation",
    "user": "postgres",
    "password": "postgres",
    # "host": os.getenv("DB_HOST", "db"),
     "host": "db",
    "port": "5432"
}

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(module)s:%(lineno)d - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed'
        }
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG'
    }
}

RETRY_CONFIG = {
    'api': {  # Добавляем секцию для API
        'max_retries': 5,
        'backoff_factor': 0.5
    },
    'db': {
        'max_retries': 3,
        'initial_delay': 1
    }
}