import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 100
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

hw_logger = logging.getLogger('homework.py')
hw_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logging_formater = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
)
handler.setFormatter(logging_formater)
hw_logger.addHandler(handler)

env_vars = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]


def send_message(bot, message):
    """Отправка сообщения ботом."""
    try:
        result = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError:
        hw_logger.error('Сообщение не отправлено')
    else:
        hw_logger.info(f'Сообщение отправлено {result.chat.username}')


def get_api_answer(current_timestamp):
    """Запрос к сервису Y.Homework."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params=params
    )
    if response.status_code == 200:
        hw_logger.info('Ответ получен')
        return response.json()
    else:
        hw_logger.error(
            f'Ошибка при обращении к сервису. '
            f'Статус: {response.status_code} '
            f'Текст: {response.text}'
        )


def check_response(response):
    """Проверка ответа от сервиса."""
    if ((type(response) is not dict)
            or (type(response.get('homeworks')) is not list)):
        hw_logger.error('Ошибка в типах полученных данных.')
        raise TypeError
    if len(response) < 1:
        hw_logger.error('Получен пустой ответ.')
        raise exceptions.ErrorInvalidResponse
    return response.get('homeworks')


def parse_status(homework):
    """Формирование сообщения для бота."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES.get(homework_status)
    else:
        hw_logger.error(
            'В ответе обнаружен недокументированный статус домашней работы'
        )
        raise KeyError
    if (homework_name is not None) and (homework_status is not None):
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        hw_logger.info(
            'Изменений статусов дз не обнаружено'
        )
        return None


def check_tokens():
    """Проверка, что все переменные окружения доступны."""
    is_exist = True
    if (PRACTICUM_TOKEN is None
            or TELEGRAM_CHAT_ID is None
            or TELEGRAM_TOKEN is None):
        hw_logger.critical('Одна или более переменных окружения не определены')
        is_exist = False
    return is_exist


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise exceptions.ErrorTokenValue(
            'Одна или более переменных окружения не определены'
        )
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except telegram.error.TelegramError:
        hw_logger.critical('Бот не инициализирован')
    else:
        current_timestamp = int(time.time())
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                current_timestamp = response['current_date']
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                time.sleep(RETRY_TIME)
            else:
                for homework in homeworks:
                    message = parse_status(homework)
                    if message is not None:
                        send_message(bot, message)
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
