import csv
import json
import os
import datetime

# Versioning
version = datetime.datetime.now().strftime("v%Y%m%d_%H%M")
generated_files = []

def save_versioned_html(filename, content):
    base, ext = os.path.splitext(filename)
    versioned_name = f"{base}_{version}{ext}"
    with open(versioned_name, "w", encoding="utf-8") as f:
        f.write(content)
    # Also save as "latest" for easy stable access
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    generated_files.append((filename, versioned_name))

nom = {}
nom_by_name = {} # Separate dictionary for name-based lookups
with open('Nomenclature.tsv', 'r', encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        nom[r['Short_Code']] = r
        nom_by_name[r['Name']] = r

bom_list = []
with open('BOM.tsv', 'r', encoding='utf-8') as f:
    bom_list = list(csv.DictReader(f, delimiter='\t'))

def explode_bom(parent_code, target_qty, results=None):
    if results is None: results = {}
    
    # Get Parent's Standard yield from Nomenclature
    # (Divide child quantity by parent yield to get 'per unit' ratio)
    p_data = nom.get(parent_code)
    try:
        p_std = float(p_data['Standard_Output_Amount'])
    except:
        p_std = 1.0 # default for sales items/portions
    
    for row in bom_list:
        if row['Parent_Code'] == parent_code:
            child_code = row['Child_Code']
            # child_req = (row_quantity_gross / parent_std_output) * parent_total_qty
            try:
                child_qty_gross = float(row['QuantityGross'])
            except:
                continue
                
            child_req_total = (child_qty_gross / p_std) * target_qty
            
            if child_code.startswith('PF-'):
                results[child_code] = results.get(child_code, 0) + child_req_total
                # Recurse
                explode_bom(child_code, child_req_total, results)
    return results

with open('drive_links.json', 'r', encoding='utf-8') as f:
    drive_links = json.load(f)

photo_map = {
    "Fresh Carrot": "fresh carrot.jpg",
    "Onion": "fresh onion.jpg",
    "Olive Oil EV": "olive oil.jpg",
    "Raw Beetroot": "fresh beetroot.jpg",
    "Fresh Potato": "fresh potato.jpg",
    "Lemon Juice": "lemon juice.jpg",
    "Garlic": "garlik.jpg",
    "SF Baked Beetroot": "baked beetroot.jpg",
    "SF Borsch Base (Vacuum)": "borsh.jpeg", 
    "Sous-vide Chicken": "Sous-vide Chicken.jpg",
    "Red Beans": "Red Beans.jpg",
    "Sour Cream": "Sour Cream.jpg",
    "Greens": "greens.jpg",
    "Borsch Bio-Active (portion)": "borsh.jpeg"
}

doc_url = drive_links.get("Borsch.pdf", "")

# 1. NOMENCLATURE OPERATIONAL
nom_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr>
  <th>Short_Code</th><th>Syrve_System_ID</th><th>Name</th><th>Type</th><th>OrderItemType</th><th>UsageNotes</th>
  <th>Standard_Output_Amount</th><th>Standard_Output_UOM</th><th>Syrve_Sync</th>
  <th>Photo_URL</th><th>Instruction_URL</th>
</tr>
"""
for scode, data in nom.items():
    name = data['Name']
    p_file = photo_map.get(name)
    p_url = drive_links.get(p_file, "") if p_file else ""
    i_url = doc_url if "Borsch" in name or "SF" in name else ""
    
    std_uom = data.get('Standard_Output_UOM', '')
    syrve_sync = data.get('Syrve_Sync', 'Yes')
    nom_html += f"<tr><td>{data['Short_Code']}</td><td>{data['Syrve_System_ID']}</td><td>{name}</td><td>{data['Type']}</td>"
    nom_html += f"<td>{data['OrderItemType']}</td><td>{data['UsageNotes']}</td>"
    nom_html += f"<td>{data['Standard_Output_Amount']}</td><td>{std_uom}</td>"
    nom_html += f"<td>{syrve_sync}</td><td>{p_url}</td><td>{i_url}</td></tr>\n"
nom_html += "</table></body></html>"

save_versioned_html("Nomenclature_Operational_table.html", nom_html)

# 2. PRODUCTION FLOW OPERATIONAL
flow_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr>
  <th>Product_Code</th><th>Product_Name</th><th>Operation</th><th>Equipment_ID</th>
  <th>Temperature</th><th>Duration_Min</th><th>Is_Bottleneck</th><th>Notes</th>
  <th>Staff_Role</th><th>Instruction_Step</th><th>Parallel_Task_Possible</th>
</tr>
"""
with open('Production_Flow.tsv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter='\t')
    for row in reader:
        op = row['Operation']
        role = "Prep Cook"
        step = ""
        parallel = "Yes"
        
        if op == "Baking":
            role = "Prep Cook"
            step = "Bake at 180°C until soft through"
            parallel = "Yes"
        elif op == "Roasting Trimmings":
            role = "Prep Cook"
            step = "Spread trimmings on GN tray; roast 200°C 20-30 min until caramelised (Maillard)"
            parallel = "Yes"
        elif op == "Sauteing":
            role = "Chef"
            step = "Saute vegetables with continuous stirring"
            parallel = "No"
        elif op == "Simmering":
            role = "Prep Cook"
            step = "Cover roasted veg with cold RO water; bring to boil, reduce to bare simmer 60-90 min"
            parallel = "Yes"
        elif op == "Straining":
            role = "Prep Cook"
            step = "Strain through fine sieve/cheesecloth; solids to compost (Zero-Waste principle)"
            parallel = "Yes"
        elif op == "Boiling Potato":
            role = "Prep Cook"
            step = "Boil borsch base until potatoes are tender"
            parallel = "Yes"
        elif op == "Cooling":
            role = "Packager"
            step = "Rapid blast chill to 3°C"
            parallel = "Yes"
        elif op == "Vacuuming":
            role = "Packager"
            step = "Vacuum seal (broth: 5L bags; borsch base: 1L bags)"
            parallel = "No"
            
        flow_html += f"<tr><td>{row['Product_Code']}</td><td>{row['Product_Name']}</td><td>{op}</td>"
        flow_html += f"<td>{row['Equipment_ID']}</td><td>{row['Temperature']}</td><td>{row['Duration_Min']}</td>"
        flow_html += f"<td>{row['Is_Bottleneck']}</td><td>{row['Notes']}</td>"
        flow_html += f"<td>{role}</td><td>{step}</td><td>{parallel}</td></tr>\n"
flow_html += "</table></body></html>"

save_versioned_html("Production_Flow_Operational_table.html", flow_html)

# 3. RESOURCE CAPACITY
cap_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr><th>Equipment_ID</th><th>Equipment_Name</th><th>Unit_Capacity</th><th>Daily_Availability_Min</th></tr>
<tr><td>L-1-K-EL-CON-OVEN-83</td><td>Convection Oven Unit 20</td><td>10 GN 1/1 Trays</td><td>480</td></tr>
<tr><td>L-2-S-INDCT-BRN-2-6</td><td>Induction Burner Unit 65</td><td>15 Liters</td><td>480</td></tr>
<tr><td>L-1-K-GAS-RNG-570-32</td><td>Gas Range Unit 32</td><td>50 Liters</td><td>480</td></tr>
<tr><td>L-1-K-BL-FRZ-790-66</td><td>Blast Chiller Unit 66</td><td>20 kg</td><td>600</td></tr>
<tr><td>L-1-K-VAC-500-67</td><td>Vacuum Sealer Unit 67</td><td>1 Bag / Minute</td><td>480</td></tr>
</table></body></html>
"""
save_versioned_html("Resource_Capacity_table.html", cap_html)

# 4. BOM Operational Costing Table
bom_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr>
  <th>Parent_Code</th><th>Parent_Name</th><th>Child_Code</th><th>Child_Name</th>
  <th>QuantityGross</th><th>Unit</th><th>Yield_Percentage</th><th>QuantityNet</th>
  <th>Unit_Cost</th><th>Total_Line_Cost</th><th>Batch_Validation</th><th>Cost_per_Sales_Unit</th>
</tr>
"""
yield_dict = {
    "Fresh Carrot": "0.8", "Onion": "0.85", "Raw Beetroot": "0.7",
    "Fresh Potato": "0.75", "Garlic": "0.95", "Processing Loss": "1"
}

with open('BOM.tsv', 'r', encoding='utf-8') as f:
    reader = list(csv.DictReader(f, delimiter='\t'))
    for idx, row in enumerate(reader):
        row_num = idx + 2
        child_name = row['Child_Name']
        y_perc = yield_dict.get(child_name, "1")
        
        qnet_formula = f"=E{row_num}*G{row_num}"
        unit_formula = f'=IFERROR(IF(COUNTIF(A:A, C{row_num})>0, SUMIF(A:A, C{row_num}, J:J)/SUMIF(A:A, C{row_num}, H:H), VLOOKUP(C{row_num}, Purchasing_Inventory!A:G, 6, FALSE)), 0)'
        total_formula = f"=E{row_num}*I{row_num}"
        # Batch_Validation:
        # For PF/RAW items: check if ROUND(SUMIF(QuantityNet), 2) == Standard_Output_Amount
        # For SALE/Compound items: check via UOM_Mapping (QuantityNet / Sale_Ratio == Standard_Output_Amount)
        parent_code = row['Parent_Code']
        valid_formula = (
            f'=IF(OR(LEFT(A{row_num},5)="SALE-", VLOOKUP(A{row_num}, Nomenclature!A:G, 4, FALSE)="Compound"), '
            f'IF(IFERROR(ROUND(SUMIF(A:A, A{row_num}, H:H) / VLOOKUP(A{row_num}, UOM_Mapping!A:G, 7, FALSE), 2), -1) '
            f'= VLOOKUP(A{row_num}, Nomenclature!A:G, 7, FALSE), "OK", "YIELD ERR"), '
            f'IF(ROUND(SUMIF(A:A, A{row_num}, H:H), 2) = VLOOKUP(A{row_num}, Nomenclature!A:G, 7, FALSE), "OK", "YIELD ERR"))'
        )
        cost_per_unit = f'=(SUMIF(A:A, A{row_num}, J:J) / SUMIF(A:A, A{row_num}, H:H)) * IFERROR(VLOOKUP(A{row_num}, UOM_Mapping!A:G, 7, FALSE), 1)'

        bom_html += f"<tr><td>{row['Parent_Code']}</td><td>{row['Parent_Name']}</td>"
        bom_html += f"<td>{row['Child_Code']}</td><td>{row['Child_Name']}</td>"
        bom_html += f"<td>{row['QuantityGross']}</td><td>{row['Unit']}</td>"
        bom_html += f"<td>{y_perc}</td><td>{qnet_formula}</td>"
        bom_html += f"<td>{unit_formula}</td><td>{total_formula}</td>"
        bom_html += f"<td>{valid_formula}</td><td>{cost_per_unit}</td></tr>\n"

bom_html += "</table></body></html>"
save_versioned_html("BOM_Operational_table.html", bom_html)

# 5. DAILY PRODUCTION PLAN
plan_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr><th>Product_Code</th><th>Product_Name</th><th>Target_Quantity</th><th>Calculated_Batches</th><th>Total_Quantity_to_Produce</th></tr>
"""

# Starting item: 100 Portions of Borsch
start_code = nom_by_name['Borsch Bio-Active (portion)']['Short_Code']
start_portions = 100
exploded = explode_bom(start_code, start_portions)

# Collect all items to plan (SALE + exploded PFs)
items_to_plan = [(start_code, start_portions)]
for code, qty in exploded.items():
    items_to_plan.append((code, qty))

# Add extra empty rows for user input
for _ in range(5):
    items_to_plan.append(("", ""))

for i, (p_code, p_qty) in enumerate(items_to_plan):
    row_num = i + 2
    # Fix ID Formula: Pull Name from Nomenclature (based on Code match)
    name_formula = f'=IFERROR(VLOOKUP(A{row_num}, Nomenclature!A:C, 3, FALSE), "")'
    # FIXED: Wrap SUMIF divisor with IFERROR to prevent #DIV/0! when PF has no BOM rows
    # (e.g. PF-VEGETABLE_BROTH has no child ingredients defined)
    batches = (
        f'=IF(A{row_num}="", 0, '
        f'IFERROR('
        f'CEILING('
        f'C{row_num} / IFERROR(VLOOKUP(A{row_num}, UOM_Mapping!A:G, 7, FALSE), 1) '
        f'/ IFERROR(VLOOKUP(A{row_num}, Nomenclature!A:G, 7, FALSE), 1), '
        f'1), 0))'
    )
    total_qty = f'=IF(A{row_num}="", 0, D{row_num} * IFERROR(VLOOKUP(A{row_num}, Nomenclature!A:G, 7, FALSE), 1))'
    
    plan_html += f"<tr><td>{p_code}</td><td>{name_formula}</td><td>{p_qty}</td><td>{batches}</td><td>{total_qty}</td></tr>\n"

plan_html += "</table></body></html>"

save_versioned_html("Daily_Production_Plan_table.html", plan_html)

# 6. RESOURCE LOAD REPORT
# Reads from Chef_Job_List via SUMIFS: sums Duration_Total_Min per Equipment_ID
load_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr><th>Equipment_ID</th><th>Equipment_Name</th><th>Total_Load_Min</th><th>Availability_Min</th><th>Status</th></tr>
"""
equipment_list = [
    ("L-1-K-EL-CON-OVEN-83", "Convection Oven Unit 20"),
    ("L-1-K-GAS-RNG-570-32", "Gas Range Unit 32"),
    ("L-1-K-BL-FRZ-790-66", "Blast Chiller Unit 66"),
    ("L-1-K-VAC-500-67", "Vacuum Sealer Unit 67")
]
for idx, (e_id, e_name) in enumerate(equipment_list):
    row_num = idx + 2
    # Sum Duration_Total_Min from Chef_Job_List where Equipment_ID matches
    total_load = f"=IFERROR(SUMIFS('Chef Job List'!F:F, 'Chef Job List'!G:G, A{row_num}), 0)"
    avail = f'=IFERROR(VLOOKUP(A{row_num}, Resource_Capacity!A:D, 4, FALSE), "Check ID mapping")'
    status = f'=IF(C{row_num} > D{row_num}, "OVERLOADED", "OK")'
    load_html += f"<tr><td>{e_id}</td><td>{e_name}</td><td>{total_load}</td><td>{avail}</td><td>{status}</td></tr>\n"
load_html += "</table></body></html>"

save_versioned_html("Resource_Load_Report_table.html", load_html)

# 7. CHEF JOB LIST
# One row per operation from Production_Flow.tsv
# Duration_Total_Min = VLOOKUP(Product_Code, Daily_Production_Plan, 4, 0) * Duration_Min
# This avoids FILTER+MMULT #REF! errors — formulas are simple cell references.
chef_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr><th>Staff_Role</th><th>Product_Code</th><th>Product_Name</th><th>Operation</th><th>Duration_Min</th><th>Duration_Total_Min</th><th>Equipment_ID</th></tr>
"""

# Role mapping from generate_operations Production_Flow Operational section
role_map = {
    "Baking":             "Prep Cook",
    "Roasting Trimmings": "Prep Cook",
    "Sauteing":           "Chef",
    "Simmering":          "Prep Cook",
    "Straining":          "Prep Cook",
    "Boiling Potato":     "Prep Cook",
    "Cooling":            "Packager",
    "Vacuuming":          "Packager",
}

with open('Production_Flow.tsv', 'r', encoding='utf-8') as f:
    pf_rows = list(csv.DictReader(f, delimiter='\t'))

for idx, row in enumerate(pf_rows):
    row_num = idx + 2  # row 2 = first data row in Sheets (row 1 = header)
    p_code = row['Product_Code']
    p_name = row['Product_Name']
    operation = row['Operation']
    equip_id = row['Equipment_ID']
    dur_min = row['Duration_Min']
    staff_role = role_map.get(operation, "Prep Cook")

    # Duration_Total_Min = Calculated_Batches (from Daily_Production_Plan col D) × Duration_Min (col E)
    # VLOOKUP(Product_Code, Daily_Production_Plan!A:D, 4) gives Calculated_Batches
    dur_total = (
        f'=IFERROR('
        f'VLOOKUP(B{row_num}, Daily_Production_Plan!A:D, 4, FALSE)'
        f' * E{row_num}, 0)'
    )

    chef_html += (
        f'<tr>'
        f'<td>{staff_role}</td>'
        f'<td>{p_code}</td>'
        f'<td>{p_name}</td>'
        f'<td>{operation}</td>'
        f'<td>{dur_min}</td>'
        f'<td>{dur_total}</td>'
        f'<td>{equip_id}</td>'
        f'</tr>\n'
    )
chef_html += "</table></body></html>"

save_versioned_html("Chef_Job_List_table.html", chef_html)

# 8. WAREHOUSE REQUEST
wh_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body><table>
<tr><th>Item_Code</th><th>Item_Name</th><th>Total_Required</th><th>Base_Unit</th><th>Packs_to_Issue</th></tr>
"""
ingredients = [
    # Purchased ingredients (issued from warehouse)
    (nom_by_name["Raw Beetroot"]["Short_Code"],   "Raw Beetroot"),
    (nom_by_name["Fresh Carrot"]["Short_Code"],   "Fresh Carrot"),
    (nom_by_name["Onion"]["Short_Code"],          "Onion"),
    (nom_by_name["Olive Oil EV"]["Short_Code"],   "Olive Oil EV"),
    (nom_by_name["Fresh Potato"]["Short_Code"],   "Fresh Potato"),
    (nom_by_name["Garlic"]["Short_Code"],         "Garlic"),
    (nom_by_name["Lemon Juice"]["Short_Code"],    "Lemon Juice"),
    (nom_by_name["Shishka Mix Spices"]["Short_Code"], "Shishka Mix Spices"),
    # Broth: only RO Water is 'purchased'; trimmings are internal waste (zero cost)
    (nom_by_name["RO Water"]["Short_Code"],       "RO Water"),
]
for idx, (i_id, i_name) in enumerate(ingredients):
    row_num = idx + 2
    # Again, use 0-defaulted batches for clean multiplication
    total_req = f"=SUMPRODUCT(SUMIFS(BOM!E:E, BOM!C:C, A{row_num}, BOM!A:A, Daily_Production_Plan!A$2:A$100), Daily_Production_Plan!D$2:D$100)"
    unit = f'=IFERROR(VLOOKUP(A{row_num}, Purchasing_Inventory!A:G, 3, FALSE), "Check ID mapping")'
    packs = f"=IFERROR(CEILING(C{row_num} / VLOOKUP(A{row_num}, Purchasing_Inventory!A:G, 5, FALSE), 1), 0)"
    wh_html += f"<tr><td>{i_id}</td><td>{i_name}</td><td>{total_req}</td><td>{unit}</td><td>{packs}</td></tr>\n"
wh_html += "</table></body></html>"

save_versioned_html("Warehouse_Request_table.html", wh_html)

# 9. INDEX HTML
index_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Syrve Tables Index - {version}</title>
<style>
    body {{ font-family: sans-serif; padding: 20px; }}
    ul {{ list-style-type: none; padding: 0; }}
    li {{ margin-bottom: 10px; padding: 10px; border-bottom: 1px solid #eee; }}
    .latest {{ font-weight: bold; color: green; }}
    .versioned {{ color: #666; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>Syrve API - Generated Tables ({version})</h1>
<p>Последняя версия выделена жирным шрифтом. Все файлы доступны по прямым ссылкам ниже.</p>
<ul>
"""
for latest, versioned in generated_files:
    index_content += f'<li><a class="latest" href="{latest}">{latest} (Latest)</a> | <a class="versioned" href="{versioned}">{versioned}</a></li>\n'
index_content += "</ul></body></html>"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(index_content)

print(f"Generated Corrected Operational Tables with version {version}")
