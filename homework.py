import logging
import os
import sys
import time
from typing import Dict, List, Union

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
VERDICTS = {
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

env_vars = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
}


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправка сообщения ботом."""
    try:
        result = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        hw_logger.info(f'Сообщение отправлено {result.chat.username}')
    except telegram.error.TelegramError:
        hw_logger.error('Сообщение не отправлено')


def get_api_answer(current_timestamp: int) -> Dict[str, Union[List, int]]:
    """Запрос к сервису Y.Homework."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as e:
        hw_logger.error('Проблема с запросом')
        raise e
    if response.status_code == 200:
        hw_logger.info('Ответ получен')
        return response.json()
    hw_logger.error(
        'Ошибка при обращении к сервису. '
        f'Статус: {response.status_code} '
        f'Текст: {response.text}'
    )
    raise exceptions.ErrorValueIsNone


def check_response(response: Dict) -> List:
    """Проверка ответа от сервиса."""
    if not isinstance(response, dict):
        hw_logger.error('Ошибка в типах полученных данных.')
        raise TypeError(f'Ожидался dict, получен {type(response)}')
    if not isinstance(response.get('homeworks'), list):
        hw_logger.error('Ошибка в типах полученных данных.')
        raise TypeError(
            'Ожидался list, получен '
            f'{type(response.get("homeworks"))}'
        )
    return response.get('homeworks')


def parse_status(homework: Dict[str, Union[str, int]]) -> str:
    """Формирование сообщения для бота."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if (homework_name is None) and (homework_status is None):
        hw_logger.info(
            'Изменений статусов дз не обнаружено'
        )
        raise exceptions.StatusNotChange
    if homework_status not in VERDICTS:
        hw_logger.error(
            'В ответе не обнаружен документированный статус домашней работы'
        )
        raise KeyError
    verdict = VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверка, что все переменные окружения доступны."""
    return (PRACTICUM_TOKEN is not None
            and TELEGRAM_CHAT_ID is not None
            and TELEGRAM_TOKEN is not None)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        hw_logger.critical("Одна или несколько переменных не определены'")
        raise exceptions.ErrorTokenValue
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
                current_timestamp = response.get('current_date')
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
