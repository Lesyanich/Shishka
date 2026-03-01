import requests
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Замените на ваши реальные значения
NOTION_TOKEN = 'your_notion_integration_token'  # Токен интеграции Notion
NOTION_DATABASE_ID = 'your_notion_database_id'  # ID базы данных "Finances" в Notion

GOOGLE_SHEET_ID = 'your_google_sheet_id'  # ID Google Sheets таблицы
GOOGLE_SHEET_RANGE = 'Sheet1!A1:D'  # Диапазон для чтения/записи (предполагаем колонки: ID, Date, Amount, Category)
SERVICE_ACCOUNT_FILE = 'path_to_your_service_account.json'  # Путь к JSON-файлу с credentials для Google API


# 1. Подключиться к Notion API
def connect_to_notion():
    headers = {
        'Authorization': f'Bearer {NOTION_TOKEN}',
        'Content-Type': 'application/json',
        'Notion-Version': '2022-06-28'  # Укажите актуальную версию API
    }
    return headers


# 2. Получить все записи из базы Finances
def get_notion_records(headers):
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    payload = {
        'page_size': 100  # Максимум 100 записей за раз, если больше - используйте пагинацию
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code != 200:
        raise Exception(f'Error fetching Notion data: {response.text}')

    data = response.json()
    records = []
    for result in data['results']:
        # Предполагаем структуру свойств: ID (title), Date (date), Amount (number), Category (select)
        properties = result['properties']
        record = {
            'id': properties.get('ID', {}).get('title', [{}])[0].get('text', {}).get('content', ''),
            'date': properties.get('Date', {}).get('date', {}).get('start', ''),
            'amount': properties.get('Amount', {}).get('number', 0),
            'category': properties.get('Category', {}).get('select', {}).get('name', '')
        }
        records.append(record)

    # Если есть пагинация (has_more), можно добавить цикл для получения всех страниц
    return records


# 3. Подключиться к Google Sheets API
def connect_to_google_sheets():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes)
    service = build('sheets', 'v4', credentials=credentials)
    return service


# 4. Сравнить данные
def compare_data(notion_records, sheet_values):
    # Предполагаем, что первая строка в Sheet - заголовки, данные начинаются со второй
    sheet_data = {row[0]: row for row in sheet_values[1:]} if sheet_values else {}  # Ключ по ID

    to_add = []
    to_update = []

    for record in notion_records:
        rec_id = record['id']
        if rec_id in sheet_data:
            sheet_row = sheet_data[rec_id]
            # Сравниваем значения (индексы: 0-ID, 1-Date, 2-Amount, 3-Category)
            if (sheet_row[1] != record['date'] or
                    float(sheet_row[2]) != record['amount'] or
                    sheet_row[3] != record['category']):
                to_update.append((rec_id, record))
        else:
            to_add.append(record)

    return to_add, to_update


# 5. Добавить/обновить строки в Google Sheets
def update_google_sheets(service, to_add, to_update):
    sheet = service.spreadsheets()

    # Сначала получаем текущие данные для определения позиций обновлений
    result = sheet.values().get(spreadsheetId=GOOGLE_SHEET_ID, range=GOOGLE_SHEET_RANGE).execute()
    sheet_values = result.get('values', [])
    sheet_data = {row[0]: idx + 1 for idx, row in enumerate(sheet_values[1:])} if len(
        sheet_values) > 1 else {}  # Индекс строк (1-based, без заголовка)

    # Обновления
    updates = []
    for rec_id, record in to_update:
        row_idx = sheet_data.get(rec_id)
        if row_idx:
            range_update = f'Sheet1!A{row_idx + 1}:D{row_idx + 1}'  # +1 потому что sheet_values[0] - заголовок
            values = [[record['id'], record['date'], record['amount'], record['category']]]
            updates.append({
                'range': range_update,
                'values': values
            })

    # Добавления
    if to_add:
        next_row = len(sheet_values) + 1
        add_values = [[rec['id'], rec['date'], rec['amount'], rec['category']] for rec in to_add]
        range_add = f'Sheet1!A{next_row}:D{next_row + len(to_add) - 1}'
        updates.append({
            'range': range_add,
            'values': add_values
        })

    if updates:
        body = {
            'valueInputOption': 'RAW',
            'data': updates
        }
        sheet.batchUpdate(spreadsheetId=GOOGLE_SHEET_ID, body=body).execute()


# Основная функция
def sync_data():
    notion_headers = connect_to_notion()
    notion_records = get_notion_records(notion_headers)

    sheets_service = connect_to_google_sheets()

    # Получаем данные из Google Sheets
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEET_ID, range=GOOGLE_SHEET_RANGE).execute()
        sheet_values = result.get('values', [])
    except HttpError as err:
        raise Exception(f'Error fetching Google Sheets data: {err}')

    to_add, to_update = compare_data(notion_records, sheet_values)

    update_google_sheets(sheets_service, to_add, to_update)
    print('Синхронизация завершена.')


# Запуск
if __name__ == '__main__':
    sync_data()