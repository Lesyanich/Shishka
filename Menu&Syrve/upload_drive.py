import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Scopes needed for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = '1bskKhKJ4BzoRNfsRO7wbNjsQ21Apn-pb'

def authenticate():
    cred_path = 'gdisk_cred.json'
    creds = Credentials.from_service_account_file(cred_path, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def upload_file(drive_service, filepath, folder_id):
    filename = os.path.basename(filepath)
    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }
    
    # Simple mime-type guessing
    if filename.endswith('.pdf'):
        mimetype = 'application/pdf'
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        mimetype = 'image/jpeg'
    elif filename.endswith('.png'):
        mimetype = 'image/png'
    else:
        mimetype = 'application/octet-stream'

    media = MediaFileUpload(filepath, mimetype=mimetype, resumable=True)
    
    try:
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink',
            supportsAllDrives=True
        ).execute()
        
        file_id = file.get('id')
        
        # Set permission to anyone with link
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        drive_service.permissions().create(fileId=file_id, body=permission, supportsAllDrives=True).execute()
        print(f"Uploaded: {filename}")
        return {
            'id': file_id,
            'webViewLink': file.get('webViewLink'),
            'webContentLink': file.get('webContentLink')
        }
    except Exception as e:
        print(f"Error uploading {filename}: {e}")
        return None

def main():
    try:
        drive_service = authenticate()
    except Exception as e:
        print(f"Authentication failed: {e}")
        return

    files_to_upload = [
        "Техкарты/Borsch.pdf"
    ]
    
    photo_dir = "Техкарты/Photo"
    if os.path.exists(photo_dir):
        for f in os.listdir(photo_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                files_to_upload.append(os.path.join(photo_dir, f))

    results = {}
    for f_path in files_to_upload:
        if os.path.exists(f_path):
            res = upload_file(drive_service, f_path, FOLDER_ID)
            if res:
                results[os.path.basename(f_path)] = res.get('webViewLink')
        else:
            print(f"File not found: {f_path}")

    with open("drive_links.json", "w", encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
        
    print("All uploads complete. Links saved to drive_links.json")

if __name__ == '__main__':
    main()
