import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
DRIVE_FOLDER_BANK     = os.getenv("DRIVE_FOLDER_BANK", "")
DRIVE_FOLDER_SUPPLIER = os.getenv("DRIVE_FOLDER_SUPPLIER", "")
DRIVE_FOLDER_TAX      = os.getenv("DRIVE_FOLDER_TAX", "")
OPEX_SPREADSHEET_ID   = os.getenv("OPEX_SPREADSHEET_ID", "1u5eZ4A5kyIm6HLGDicdOXAW2if-PhWMiav-VtwVz8po")

# Sheets
SHEET_EXPENSES = "Expenses"
SHEET_CAPEX = "Capex"
SHEET_OPEX = "Opex"
SHEET_REF_SUPPLIERS = "REF_Suppliers"
SHEET_REF_CATEGORIES = "REF_Categories"
SHEET_REF_SUB_CATEGORIES = "REF_Sub_Categories"

# Expenses columns order (0-indexed)
EXPENSES_COLS = [
    "transaction_id",   # A
    "date",             # B
    "flow_type",        # C  CapEx / OpEx
    "category_id",      # D
    "category_name",    # E
    "contractor_id",    # F
    "subcategory_id",   # G
    "subcategory_name", # H
    "contractor_name",  # I
    "details",          # J
    "amount",           # K
    "currency",         # L
    "comment",          # M
    "chosen_currency",  # N  formatted
    "type",             # O  operating / One-time
    "location",         # P
    "paid_by",          # Q
    "payment_method",   # R
    "input_source",     # S
    "status",           # T
    "link_supplier",    # U
    "link_bank",        # V
]

FLOW_TYPES = ["OpEx", "CapEx"]
LOCATIONS = ["L1 Sayan", "L2 Tops", "General"]
PAID_BY = ["Lesya", "Bas"]
PAYMENT_METHODS = ["Lesya's Bangkok bank", "Bas UEA", "Cash", "Bas UEA Alla"]
CURRENCIES = ["THB", "USD", "AED"]
STATUSES = ["paid", "on hold"]
INPUT_SOURCE = "Bot"
