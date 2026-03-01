import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = '1bskKhKJ4BzoRNfsRO7wbNjsQ21Apn-pb'
cred_path = 'gdisk_cred.json'
creds = Credentials.from_service_account_file(cred_path, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

try:
    folder = drive_service.files().get(fileId=FOLDER_ID, supportsAllDrives=True).execute()
    print("Folder found:", folder['name'])
except Exception as e:
    print("Error:", e)
