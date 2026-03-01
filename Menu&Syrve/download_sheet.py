import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = '1-bNwX3XkDiYADdJ1AuoqQM4YhvKSMxnJ_QkMuPGU2u8'

def authenticate():
    cred_path = 'gdisk_cred.json'
    creds = Credentials.from_service_account_file(cred_path, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def main():
    try:
        service = authenticate()
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='BOM!A1:J100', valueRenderOption='UNFORMATTED_VALUE', dateTimeRenderOption='FORMATTED_STRING').execute()
        values = result.get('values', [])
        
        # Also let's get formulas
        result_formulas = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='BOM!A1:J100', valueRenderOption='FORMULA').execute()
        formulas = result_formulas.get('values', [])

        if not values:
            print('No data found.')
        else:
            for i, row in enumerate(values):
                form_row = formulas[i] if i < len(formulas) else []
                print(f"Row {i+1}:")
                for j, val in enumerate(row):
                    form_val = form_row[j] if j < len(form_row) else val
                    if str(val) != str(form_val):
                        print(f"  Col {j+1}: {val} (Formula: {form_val})")
                    else:
                        print(f"  Col {j+1}: {val}")
    except Exception as e:
        print(f"Error accessing spreadsheet: {e}")

if __name__ == '__main__':
    main()
