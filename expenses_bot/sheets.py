"""Google Sheets read/write helpers."""
import re
from datetime import date
from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import (
    SPREADSHEET_ID, GOOGLE_CREDS_FILE,
    SHEET_EXPENSES, SHEET_CAPEX, SHEET_REF_SUPPLIERS,
    SHEET_REF_CATEGORIES, SHEET_REF_SUB_CATEGORIES,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_service = None


def _get_service():
    global _service
    if _service is None:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDS_FILE, scopes=SCOPES
        )
        _service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _service


def _read(range_: str) -> list[list]:
    result = _get_service().spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=range_
    ).execute()
    return result.get("values", [])


def _find_next_row(sheet: str, date_col: str = "B") -> int:
    """Find the first truly empty row by scanning the date column."""
    rows = _get_service().spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!{date_col}2:{date_col}2000",
        majorDimension="COLUMNS",
    ).execute().get("values", [[]])[0]
    # rows is a flat list of values in col B starting from row 2
    # Find last non-empty entry
    last_idx = -1
    for i, v in enumerate(rows):
        if str(v).strip():
            last_idx = i
    return last_idx + 3  # +2 for 1-indexed +1 for header, +1 for next empty


def _write_row(sheet: str, row_num: int, row: list):
    """Write a row to a specific row number."""
    col_end = chr(ord("A") + len(row) - 1)
    _get_service().spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!A{row_num}:{col_end}{row_num}",
        valueInputOption="USER_ENTERED",
        body={"values": [row]},
    ).execute()


# ── Reference data ────────────────────────────────────────────────────────────

def get_suppliers() -> list[dict]:
    rows = _read(f"{SHEET_REF_SUPPLIERS}!A2:Q200")
    return [
        {"id": r[0], "name": r[1] if len(r) > 1 else ""}
        for r in rows if r
    ]


def get_categories() -> list[dict]:
    rows = _read(f"{SHEET_REF_CATEGORIES}!A2:E50")
    return [
        {"code": r[0], "name": r[1], "asset_expense": r[2] if len(r) > 2 else ""}
        for r in rows if r
    ]


def get_subcategories() -> list[dict]:
    rows = _read(f"{SHEET_REF_SUB_CATEGORIES}!A2:D100")
    return [
        {"parent": r[0], "code": r[1], "name": r[2] if len(r) > 2 else ""}
        for r in rows if r
    ]


# ── Transaction ID generation ─────────────────────────────────────────────────

def generate_transaction_id(tx_date: str) -> str:
    """
    tx_date: DD.MM.YYYY
    Format: YYYYMMDDNNN  (NNN = 001, 002, …)
    Reads only col A up to the actual last data row.
    """
    parts = tx_date.strip().split(".")
    date_prefix = f"{parts[2]}{parts[1]}{parts[0]}"  # YYYYMMDD

    next_row = _find_next_row(SHEET_EXPENSES)
    rows = _read(f"{SHEET_EXPENSES}!A2:A{next_row}")
    existing = [r[0] for r in rows if r and str(r[0]).startswith(date_prefix)]
    seq = len(existing) + 1
    return f"{date_prefix}{seq:03d}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_num(val):
    """Convert amount to float for Sheets API (avoids locale decimal issues)."""
    if val is None:
        return ""
    try:
        return float(str(val).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError):
        return val


# ── Suppliers ─────────────────────────────────────────────────────────────────

def add_supplier(name: str) -> str:
    """Add a new supplier to REF_Suppliers. Returns the new SUP-NNN id."""
    existing_ids = _read(f"{SHEET_REF_SUPPLIERS}!A2:A200")
    nums = []
    for r in existing_ids:
        if r and str(r[0]).startswith("SUP-"):
            try:
                nums.append(int(str(r[0])[4:]))
            except ValueError:
                pass
    next_num = max(nums, default=0) + 1
    new_id = f"SUP-{next_num:03d}"
    next_row = _find_next_row(SHEET_REF_SUPPLIERS, date_col="A")
    _write_row(SHEET_REF_SUPPLIERS, next_row, [new_id, name, "", "", "", "", "", "", "Active"])
    return new_id


# ── Expenses ──────────────────────────────────────────────────────────────────

def format_amount(amount: str | float, currency: str) -> str:
    try:
        val = float(str(amount).replace(",", "").replace(" ", ""))
        if val == int(val):
            formatted = f"{int(val):,}".replace(",", "\u00a0")
        else:
            formatted = f"{val:,.2f}".replace(",", "\u00a0")
        return f"{formatted} "
    except Exception:
        return str(amount)


def update_expense_cells(sheet_row: int, updates: dict):
    """
    Update specific cells in an Expenses row.
    updates: {col_letter: value}  e.g. {"I": "Google LLC", "F": "SUP-036"}
    Only the supplied cells are written — everything else stays untouched.
    """
    data_list = [
        {"range": f"{SHEET_EXPENSES}!{col}{sheet_row}", "values": [[val]]}
        for col, val in updates.items()
    ]
    if not data_list:
        return
    _get_service().spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": data_list},
    ).execute()


def append_expense(data: dict) -> str:
    """Append a row to Expenses. Returns generated transaction_id."""
    tx_id = generate_transaction_id(data["date"])
    amount_fmt = format_amount(data["amount"], data["currency"])

    row = [
        tx_id,
        data["date"],
        data["flow_type"],
        data.get("category_id", ""),
        data.get("category_name", ""),
        data.get("contractor_id", ""),
        data.get("subcategory_id", ""),
        data.get("subcategory_name", ""),
        data.get("contractor_name", ""),
        data.get("details", ""),
        _to_num(data.get("amount")),
        data["currency"],
        data.get("comment", ""),
        amount_fmt,
        data.get("type", ""),
        data.get("location", ""),
        data.get("paid_by", ""),
        data.get("payment_method", ""),
        data.get("input_source", "Bot"),
        data.get("status", "paid"),
        data.get("link_supplier", ""),
        data.get("link_bank", ""),
    ]
    next_row = _find_next_row(SHEET_EXPENSES)
    _write_row(SHEET_EXPENSES, next_row, row)
    return tx_id
