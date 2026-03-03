"""Google Drive — upload receipt files with folder routing."""
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from config import (
    GOOGLE_CREDS_FILE,
    DRIVE_FOLDER_BANK,
    DRIVE_FOLDER_SUPPLIER,
    DRIVE_FOLDER_TAX,
    GOOGLE_DRIVE_FOLDER_ID,
)

# File type → folder mapping
FOLDER_MAP = {
    "bank":     DRIVE_FOLDER_BANK,      # скрины из банковского приложения
    "supplier": DRIVE_FOLDER_SUPPLIER,  # чеки от поставщиков
    "tax":      DRIVE_FOLDER_TAX,       # tax invoices для налоговой
}

SCOPES = ["https://www.googleapis.com/auth/drive"]

_service = None


def _get_service():
    global _service
    if _service is None:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDS_FILE, scopes=SCOPES
        )
        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _service


def get_folder_id(doc_type: str) -> str:
    """
    doc_type: 'bank' | 'supplier' | 'tax'
    Falls back to root folder if specific one not configured.
    """
    fid = FOLDER_MAP.get(doc_type, "")
    return fid or GOOGLE_DRIVE_FOLDER_ID


def upload_file(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "image/jpeg",
    doc_type: str = "bank",
) -> str:
    """
    Upload a file to the appropriate Drive folder.
    doc_type: 'bank' | 'supplier' | 'tax'
    Supports both My Drive and Shared Drives.
    Returns the file's web view link, or '' if no folder configured.
    """
    folder_id = get_folder_id(doc_type)
    if not folder_id:
        return ""

    metadata = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type)

    file = (
        _get_service()
        .files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,webViewLink",
            supportsAllDrives=True,          # ← required for Shared Drives
        )
        .execute()
    )

    # Try to make publicly viewable (may fail on Shared Drives — that's OK)
    try:
        _get_service().permissions().create(
            fileId=file["id"],
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()
    except Exception:
        pass  # Shared Drive may restrict external sharing — link still works internally

    return file.get("webViewLink", "")


def check_folders() -> dict:
    """Check which Drive folders are accessible. Returns {name: ok/error}."""
    results = {}
    for name, fid in FOLDER_MAP.items():
        if not fid:
            results[name] = "not configured"
            continue
        try:
            f = _get_service().files().get(
                fileId=fid,
                fields="id,name",
                supportsAllDrives=True,      # ← required for Shared Drives
            ).execute()
            results[name] = f"OK: {f['name']}"
        except Exception as ex:
            results[name] = f"ERROR: {ex}"
    return results
