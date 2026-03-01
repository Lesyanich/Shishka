import csv
import urllib.request
import os
import datetime

# Versioning
version = datetime.datetime.now().strftime("v%Y%m%d_%H%M")

def save_versioned_html(filename, content):
    base, ext = os.path.splitext(filename)
    versioned_name = f"{base}_{version}{ext}"
    with open(versioned_name, "w", encoding="utf-8") as f:
        f.write(content)
    # Also save as "latest" for easy stable access
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

# Read Nomenclature
nom = {}
with open('Nomenclature.tsv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    for row in reader:
        nom[row['Name'].strip()] = row['Short_Code'].strip()

def get_code(name):
    code = nom.get(name.strip())
    if not code:
        print(f"WARNING: No Short_Code found for item '{name}'")
    return code or "MISSING_CODE"

purchasing_data = [
    # Item_Name, Purchase_Unit, Purchase_Price, Base_Unit_Ratio
    # ── Purchased Raw Ingredients ────────────────────────────────────────────
    ("Fresh Carrot",           "kg",          "50",  "1"),
    ("Onion",                  "kg",          "40",  "1"),
    ("Olive Oil EV",           "Bottle 1L",   "800", "1"),
    ("Raw Beetroot",           "kg",          "35",  "1"),
    ("Fresh Potato",           "kg",          "45",  "1"),
    ("Lemon Juice",            "Bottle 1L",   "300", "1"),
    ("Garlic",                 "kg",          "250", "1"),
    ("Shishka Mix Spices",     "Pack 500g",   "600", "0.5"),
    # ── Zero-Waste Broth Inputs (cost=0; these are internal trimming by-products) ──
    ("RO Water",               "Liter",       "2",   "1"),   # nominal water cost
    ("Root Trimmings",         "kg",          "0",   "1"),   # carrot/celery offcuts
    ("Onion Trimmings",        "kg",          "0",   "1"),   # outer layers
    ("Herb Stems",             "kg",          "0",   "1"),   # cilantro/parsley/dill
    ("Mushroom Stems",         "kg",          "0",   "1"),   # champignon / lion's mane
    ("Cabbage Cores",          "kg",          "0",   "1"),   # cauliflower/broccoli cores
    # ── Modifiers (purchased) ────────────────────────────────────────────────
    ("Sous-vide Chicken",      "kg",          "450", "1"),
    ("Red Beans",              "Can 400g",    "120", "0.4"),
    ("Sour Cream",             "Bucket 1kg",  "350", "1"),
    ("Coconut Yogurt",         "Bucket 1kg",  "550", "1"),
    ("Ancient Crunch",         "kg",          "800", "1"),
    ("Greens",                 "kg",          "600", "1"),
]

# Generate Purchasing_Inventory HTML
purch_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr>
  <th>SKU_ID</th><th>Item_Name</th><th>Purchase_Unit</th>
  <th>Purchase_Price</th><th>Base_Unit_Ratio</th><th>Price_per_Base_Unit</th><th>Last_Updated</th>
</tr>
"""
for idx, item in enumerate(purchasing_data):
    name, p_unit, p_price, ratio = item
    code = get_code(name)
    row_num = idx + 2
    formula = f"=D{row_num}/E{row_num}"
    purch_html += f"<tr><td>{code}</td><td>{name}</td><td>{p_unit}</td><td>{p_price}</td><td>{ratio}</td><td>{formula}</td><td>2026-03-01</td></tr>\n"
purch_html += "</table></body></html>"

save_versioned_html("Purchasing_Inventory_table.html", purch_html)

# Real Yield percentages based on common culinary averages
yield_dict = {
    "Fresh Carrot": "0.8", # 80% after peeling/trimming
    "Onion": "0.85",
    "Raw Beetroot": "0.7", # 70% after baking/peeling as requested
    "Fresh Potato": "0.75",
    "Garlic": "0.95"
}

bom_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr>
  <th>Parent_Code</th><th>Parent_Name</th><th>Child_Code</th><th>Child_Name</th>
  <th>QuantityGross</th><th>Unit</th><th>Yield_Percentage</th><th>QuantityNet</th>
  <th>Unit_Cost</th><th>Total_Line_Cost</th>
</tr>
"""

with open('BOM.tsv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    for idx, row in enumerate(reader):
        row_num = idx + 2
        child_name = row['Child_Name']
        y_perc = yield_dict.get(child_name, "1")
        
        # formulas for Google Sheets (QuantityNet = Gross * Yield)
        qnet_formula = f"=E{row_num}*G{row_num}"
        
        # Unit Cost Formula: (Cascade logic)
        # If Child_ID is present as a Parent_ID, calculate its unit cost from nested ingredients.
        # Else, lookup from Purchasing_Inventory.
        # The sum of Total_Line_Cost for all ingredients of the SF / The sum of QuantityNet.
        unit_formula = f'=IFERROR(IF(COUNTIF(A:A, C{row_num})>0, SUMIF(A:A, C{row_num}, J:J)/SUMIF(A:A, C{row_num}, H:H), VLOOKUP(C{row_num}, Purchasing_Inventory!A:G, 6, FALSE)), 0)'
        
        # Total Line Cost Formula (Gross Weight * Unit Cost)
        total_formula = f"=E{row_num}*I{row_num}"
        
        bom_html += f"<tr><td>{row['Parent_Code']}</td><td>{row['Parent_Name']}</td>"
        bom_html += f"<td>{row['Child_Code']}</td><td>{row['Child_Name']}</td>"
        bom_html += f"<td>{row['QuantityGross']}</td><td>{row['Unit']}</td>"
        bom_html += f"<td>{y_perc}</td><td>{qnet_formula}</td>"
        bom_html += f"<td>{unit_formula}</td><td>{total_formula}</td></tr>\n"

bom_html += "</table></body></html>"

save_versioned_html("BOM_Costing_table.html", bom_html)

print("Food Costing HTML tables generated successfully.")
