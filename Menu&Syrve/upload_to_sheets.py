"""
upload_to_sheets.py
Reads all generated HTML tables and pushes them to the corresponding sheets
in the Google Spreadsheet. Uses PyJWT + cryptography (no google-auth needed).
"""

import json, time, re, urllib.request, urllib.parse
from html.parser import HTMLParser

import jwt  # PyJWT

# ─── Config ─────────────────────────────────────────────────────────────────
SPREADSHEET_ID = '1-bNwX3XkDiYADdJ1AuoqQM4YhvKSMxnJ_QkMuPGU2u8'
CRED_FILE      = 'gdisk_cred.json'
SCOPES         = 'https://www.googleapis.com/auth/spreadsheets'
TOKEN_URL      = 'https://oauth2.googleapis.com/token'

# Map: local HTML file → Sheet name in Google Sheets
SHEET_MAP = [
    # ── Syrve Catalogue Structure (v2) ─────────────────────────────────────────
    ('Groups_table.html',                     'Groups'),
    ('Product_Categories_table.html',         'Product_Categories'),
    ('Modifier_Schema_Registry_table.html',   'Modifier_Schemas'),
    # ── Core Menu Data ──────────────────────────────────────────────────────────
    ('Nomenclature_Operational_table.html',   'Nomenclature'),
    ('BOM_Operational_table.html',            'BOM'),
    ('Modifier_Schemes.tsv',                  'Modifier_Schemes'),
    # ── Production & Planning ───────────────────────────────────────────────────
    ('Purchasing_Inventory_table.html',       'Purchasing_Inventory'),
    ('Daily_Production_Plan_table.html',      'Daily_Production_Plan'),
    ('Production_Flow_Operational_table.html','Production_Flow'),
    ('Resource_Capacity_table.html',          'Resource_Capacity'),
    ('Resource_Load_Report_table.html',       'Resource Load Report'),
    ('Chef_Job_List_table.html',              'Chef Job List'),
    ('Warehouse_Request_table.html',          'Warehouse Request'),
    ('UOM_Mapping_table.html',               'UOM_Mapping'),
    # ── Costing Breakdown (v3) ──────────────────────────────────────────────────
    ('Modifier_Costs_table.html',            'Modifier_Costs'),
    ('Dish_Cost_Summary_table.html',         'Dish_Cost_Summary'),
]

# ─── Auth ────────────────────────────────────────────────────────────────────
def get_access_token():
    with open(CRED_FILE) as f:
        cred = json.load(f)

    now = int(time.time())
    payload = {
        "iss":   cred["client_email"],
        "scope": SCOPES,
        "aud":   TOKEN_URL,
        "iat":   now,
        "exp":   now + 3600,
    }
    private_key = cred["private_key"]
    signed_jwt  = jwt.encode(payload, private_key, algorithm="RS256")

    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion":  signed_jwt,
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]


# ─── Sheets helpers ───────────────────────────────────────────────────────────
def sheets_request(method, url, token, body=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"    HTTP {e.code}: {e.read().decode()[:300]}")
        return None


def clear_sheet(token, sheet_name):
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}"
           f"/values/{urllib.parse.quote(sheet_name)}!A1:ZZ:clear")
    sheets_request("POST", url, token)


def write_rows(token, sheet_name, rows):
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}"
           f"/values/{urllib.parse.quote(sheet_name)}!A1"
           f"?valueInputOption=USER_ENTERED")
    body = {"values": rows}
    return sheets_request("PUT", url, token, body)


# ─── HTML table parser ───────────────────────────────────────────────────────
class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._cur_row, self._cur_cell, self._in_cell = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self._cur_row = []
        elif tag in ('td', 'th'):
            self._cur_cell, self._in_cell = [], True

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._in_cell:
            self._cur_row.append(''.join(self._cur_cell).strip())
            self._in_cell = False
        elif tag == 'tr' and self._cur_row is not None:
            self.rows.append(self._cur_row)
            self._cur_row = None

    def handle_data(self, data):
        if self._in_cell:
            self._cur_cell.append(data)


def parse_html_table(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    p = TableParser()
    p.feed(content)
    return p.rows


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("🔑  Getting access token via service account JWT…")
    token = get_access_token()
    print(f"✅  Token obtained.\n📋  Spreadsheet: {SPREADSHEET_ID}\n")

    for html_file, sheet_name in SHEET_MAP:
        print(f"📄  {html_file} → [{sheet_name}]")
        try:
            rows = parse_html_table(html_file)
            if not rows:
                print(f"    ⚠  Empty table, skipping.")
                continue
            clear_sheet(token, sheet_name)
            result = write_rows(token, sheet_name, rows)
            if result:
                updated = result.get("updatedCells", "?")
                print(f"    ✅  {len(rows)} rows, {updated} cells written.")
            else:
                print(f"    ❌  Write failed (see error above).")
        except FileNotFoundError:
            print(f"    ❌  File not found: {html_file}")
        except Exception as e:
            print(f"    ❌  {e}")

    print("\n🎉  Upload complete!")


if __name__ == '__main__':
    main()
