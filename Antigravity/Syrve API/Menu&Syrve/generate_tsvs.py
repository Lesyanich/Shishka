import uuid
import csv
from decimal import Decimal, ROUND_HALF_UP

NAMESPACE = uuid.UUID('12345678-1234-5678-1234-567812345678')

def generate_uuid(name):
    return str(uuid.uuid5(NAMESPACE, name))

# ─────────────────────────────────────────────────────────────────────────────
# 0. GROUPS  (Syrve product tree — top-level folders)
# (Code, Name, Parent_Code, Description)
# ─────────────────────────────────────────────────────────────────────────────
groups_data = [
    ("GRP-INGREDIENTS", "Raw Ingredients",     "",                "Purchased raw materials"),
    ("GRP-ZEROWASTE",   "Zero-Waste Inputs",   "GRP-INGREDIENTS", "Kitchen by-product trimmings; cost=0"),
    ("GRP-SF",          "Semi-Finished",       "",                "Kitchen-produced SF products"),
    ("GRP-MODIFIERS",   "Modifiers & Add-ons", "",                "Guest-facing customisation items and groups"),
    ("GRP-SALE",        "Sale Menu",           "",                "Items sold directly to guests"),
]
groups = {code: {"sys_id": generate_uuid(name), "name": name,
                 "parent": parent, "desc": desc}
          for code, name, parent, desc in groups_data}

# ─────────────────────────────────────────────────────────────────────────────
# 0b. PRODUCT CATEGORIES  (cross-cutting classification within groups)
# (Code, Name, Group_Code)
# ─────────────────────────────────────────────────────────────────────────────
categories_data = [
    ("CAT-VEGETABLES",  "Vegetables & Roots",     "GRP-INGREDIENTS"),
    ("CAT-LIQUIDS",     "Oils, Juices & Liquids", "GRP-INGREDIENTS"),
    ("CAT-SPICES",      "Spices & Mixes",         "GRP-INGREDIENTS"),
    ("CAT-ZEROWASTE",   "Zero-Waste By-products", "GRP-ZEROWASTE"),
    ("CAT-SOUPS_SF",    "Soup Bases (SF)",        "GRP-SF"),
    ("CAT-PROTEINS",    "Protein Add-ons",        "GRP-MODIFIERS"),
    ("CAT-TOPPINGS",    "Toppings & Dairy",       "GRP-MODIFIERS"),
    ("CAT-SOUPS_SALE",  "Functional Soups",       "GRP-SALE"),
]
categories = {code: {"sys_id": generate_uuid(name), "name": name, "group": grp}
              for code, name, grp in categories_data}

# ─────────────────────────────────────────────────────────────────────────────
# 0c. MODIFIER SCHEMA REGISTRY
# (Code, Name, Dish_Short_Code)  — one schema per dish that has modifiers
# ─────────────────────────────────────────────────────────────────────────────
schemas_data = [
    ("SCH-BORSCH", "Borsch Bio-Active Add-ons", "SALE-BORSCH_BIOACTIVE"),
]
schemas = {code: {"sys_id": generate_uuid(name), "name": name, "dish_code": dish}
           for code, name, dish in schemas_data}
dish_to_schema = {dish: code for code, name, dish in schemas_data}

# ─────────────────────────────────────────────────────────────────────────────
# 1. NOMENCLATURE  (base fields)
# Tuple: (Name, Type, OIT, StdOut, StdOutUOM, Prefix, Syrve_Sync)
# ─────────────────────────────────────────────────────────────────────────────
items = [
    # ── Purchased Raw Ingredients ─────────────────────────────────────────────
    ("Fresh Carrot",          "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Onion",                 "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Olive Oil EV",          "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Raw Beetroot",          "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Fresh Potato",          "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Lemon Juice",           "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Garlic",                "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Shishka Mix Spices",    "good",           "Product",  "",   "",        "RAW",  "Yes"),
    # ── Zero-Waste Broth Inputs (cost=0) ─────────────────────────────────────
    ("RO Water",              "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Root Trimmings",        "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Onion Trimmings",       "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Herb Stems",            "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Mushroom Stems",        "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Cabbage Cores",         "good",           "Product",  "",   "",        "RAW",  "Yes"),
    # ── Semi-Finished ─────────────────────────────────────────────────────────
    ("SF Vegetable Broth Zero-Waste", "dish",   "Product",  "10", "l",       "PF",   "Yes"),
    ("SF Mirepoix (Saute)",           "dish",   "Product",  "1",  "kg",      "PF",   "Yes"),
    ("SF Baked Beetroot",             "dish",   "Product",  "1",  "kg",      "PF",   "Yes"),
    ("SF Borsch Base (Vacuum)",       "dish",   "Product",  "10", "l",       "PF",   "Yes"),
    # ── Modifiers & Groups ────────────────────────────────────────────────────
    ("Sous-vide Chicken",     "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Red Beans",             "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Sour Cream",            "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Coconut Yogurt",        "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Ancient Crunch",        "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Greens",                "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Add-ons (Protein)",     "modifier_group", "",         "",   "",        "MOD",  "Yes"),
    ("Toppings",              "modifier_group", "",         "",   "",        "MOD",  "Yes"),
    # ── Sale Dishes ───────────────────────────────────────────────────────────
    ("Borsch Bio-Active (portion)", "dish",     "Compound", "1",  "portion", "SALE", "Yes"),
    # ── Internal Accounting ───────────────────────────────────────────────────
    ("Processing Loss",       "service",        "",         "",   "",        "LOSS", "No"),
]

def make_short_code(name, prefix):
    clean = "".join(c for c in name if c.isalnum() or c.isspace()).upper()
    parts = clean.split()
    if prefix == "PF" and parts[0] == "SF":
        parts = parts[1:]
    return f"{prefix}-{'_'.join(parts[:2])}"

nom = {name: {
    "sys_id":        generate_uuid(name) if name != "Processing Loss" else "LOSS-001",
    "short_code":    make_short_code(name, prefix),
    "type":          t,
    "orderItemType": oit,
    "std_out":       std,
    "std_uom":       std_uom,
    "syrve_sync":    syrve_sync,
} for name, t, oit, std, std_uom, prefix, syrve_sync in items}

# ─────────────────────────────────────────────────────────────────────────────
# 1b. EXTENDED SYRVE FIELDS  per item
# (measureUnit, groupCode, categoryCode, kcal/100g, prot/100g, fat/100g, carb/100g)
# Nutritional values: ESTIMATES — to be confirmed by lab analysis.
# Empty = not applicable or data pending.
# ─────────────────────────────────────────────────────────────────────────────
ext = {
    # ── Purchased Ingredients ────────────────────────────────────────────────
    "Fresh Carrot":      ("kg",     "GRP-INGREDIENTS", "CAT-VEGETABLES", "",    "",    "",    ""),
    "Onion":             ("kg",     "GRP-INGREDIENTS", "CAT-VEGETABLES", "",    "",    "",    ""),
    "Olive Oil EV":      ("l",      "GRP-INGREDIENTS", "CAT-LIQUIDS",    "",    "",    "",    ""),
    "Raw Beetroot":      ("kg",     "GRP-INGREDIENTS", "CAT-VEGETABLES", "",    "",    "",    ""),
    "Fresh Potato":      ("kg",     "GRP-INGREDIENTS", "CAT-VEGETABLES", "",    "",    "",    ""),
    "Lemon Juice":       ("l",      "GRP-INGREDIENTS", "CAT-LIQUIDS",    "",    "",    "",    ""),
    "Garlic":            ("kg",     "GRP-INGREDIENTS", "CAT-VEGETABLES", "",    "",    "",    ""),
    "Shishka Mix Spices":("kg",     "GRP-INGREDIENTS", "CAT-SPICES",     "",    "",    "",    ""),
    # ── Zero-Waste ────────────────────────────────────────────────────────────
    "RO Water":          ("l",      "GRP-ZEROWASTE",   "CAT-ZEROWASTE",  "",    "",    "",    ""),
    "Root Trimmings":    ("kg",     "GRP-ZEROWASTE",   "CAT-ZEROWASTE",  "",    "",    "",    ""),
    "Onion Trimmings":   ("kg",     "GRP-ZEROWASTE",   "CAT-ZEROWASTE",  "",    "",    "",    ""),
    "Herb Stems":        ("kg",     "GRP-ZEROWASTE",   "CAT-ZEROWASTE",  "",    "",    "",    ""),
    "Mushroom Stems":    ("kg",     "GRP-ZEROWASTE",   "CAT-ZEROWASTE",  "",    "",    "",    ""),
    "Cabbage Cores":     ("kg",     "GRP-ZEROWASTE",   "CAT-ZEROWASTE",  "",    "",    "",    ""),
    # ── Semi-Finished (production items; guest-facing nutrition N/A) ──────────
    "SF Vegetable Broth Zero-Waste": ("l",  "GRP-SF", "CAT-SOUPS_SF", "", "", "", ""),
    "SF Mirepoix (Saute)":           ("kg", "GRP-SF", "CAT-SOUPS_SF", "", "", "", ""),
    "SF Baked Beetroot":             ("kg", "GRP-SF", "CAT-SOUPS_SF", "", "", "", ""),
    "SF Borsch Base (Vacuum)":       ("l",  "GRP-SF", "CAT-SOUPS_SF",
                                      "32", "1.0", "0.4", "5.8"),  # ESTIMATE per 100g
    # ── Modifiers (nutrition per 100g, ESTIMATES) ─────────────────────────────
    "Sous-vide Chicken": ("kg", "GRP-MODIFIERS", "CAT-PROTEINS", "150", "25.0", "5.0",  "0"),
    "Red Beans":         ("kg", "GRP-MODIFIERS", "CAT-PROTEINS", "127",  "8.0", "0.5", "23"),
    "Sour Cream":        ("kg", "GRP-MODIFIERS", "CAT-TOPPINGS", "200",  "2.5","20.0",  "3"),
    "Coconut Yogurt":    ("kg", "GRP-MODIFIERS", "CAT-TOPPINGS", "160",  "5.0","12.0",  "8"),
    "Ancient Crunch":    ("kg", "GRP-MODIFIERS", "CAT-TOPPINGS", "450", "15.0","22.0", "50"),
    "Greens":            ("kg", "GRP-MODIFIERS", "CAT-TOPPINGS",  "30",  "2.5", "0.4",  "3"),
    "Add-ons (Protein)": ("",   "GRP-MODIFIERS", "",             "",    "",    "",    ""),
    "Toppings":          ("",   "GRP-MODIFIERS", "",             "",    "",    "",    ""),
    # ── Sale Dish (per 100g of base borsch, ESTIMATE; lab confirmation needed) ─
    "Borsch Bio-Active (portion)": ("portion", "GRP-SALE", "CAT-SOUPS_SALE",
                                    "35", "1.2", "0.5", "6.5"),
    # ── Internal ─────────────────────────────────────────────────────────────
    "Processing Loss":   ("",  "",  "", "", "", "", ""),
}

# ─────────────────────────────────────────────────────────────────────────────
# WRITE: Groups.tsv
# ─────────────────────────────────────────────────────────────────────────────
with open('Groups.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(["Group_Code", "Syrve_System_ID", "Group_Name", "Parent_Group_Code", "Description"])
    for code, data in groups.items():
        w.writerow([code, data["sys_id"], data["name"], data["parent"], data["desc"]])

# ─────────────────────────────────────────────────────────────────────────────
# WRITE: Product_Categories.tsv
# ─────────────────────────────────────────────────────────────────────────────
with open('Product_Categories.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(["Category_Code", "Syrve_System_ID", "Category_Name", "Parent_Group_Code"])
    for code, data in categories.items():
        w.writerow([code, data["sys_id"], data["name"], data["group"]])

# ─────────────────────────────────────────────────────────────────────────────
# WRITE: Modifier_Schema_Registry.tsv
# ─────────────────────────────────────────────────────────────────────────────
with open('Modifier_Schema_Registry.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(["Schema_Code", "Syrve_System_ID", "Schema_Name", "Dish_Short_Code"])
    for code, data in schemas.items():
        w.writerow([code, data["sys_id"], data["name"], data["dish_code"]])

# ─────────────────────────────────────────────────────────────────────────────
# WRITE: API_Mapping_Table.tsv
# ─────────────────────────────────────────────────────────────────────────────
with open('API_Mapping_Table.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(["Short_Code", "Syrve_System_ID", "Item_Name"])
    for name, data in nom.items():
        w.writerow([data["short_code"], data["sys_id"], name])

# ─────────────────────────────────────────────────────────────────────────────
# WRITE: Nomenclature.tsv  (full Syrve-ready schema)
# New columns: measureUnit, groupId, productCategoryId, modifierSchemaId,
#              kcal_per100g, protein_per100g, fat_per100g, carbs_per100g
# Note: groupId / productCategoryId store the human-readable Code;
#       the Syrve UUID is resolved via VLOOKUP to Groups/Product_Categories sheets.
# ─────────────────────────────────────────────────────────────────────────────
with open('Nomenclature.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow([
        "Short_Code", "Syrve_System_ID", "Name", "Type", "OrderItemType",
        "UsageNotes", "Standard_Output_Amount", "Standard_Output_UOM", "Syrve_Sync",
        "measureUnit", "groupId", "productCategoryId", "modifierSchemaId",
        "kcal_per100g", "protein_per100g", "fat_per100g", "carbs_per100g",
    ])
    for name, data in nom.items():
        notes = "Universal SF" if name in ["SF Mirepoix (Saute)", "SF Baked Beetroot"] else ""
        if name in ["Root Trimmings", "Onion Trimmings", "Herb Stems",
                    "Mushroom Stems", "Cabbage Cores"]:
            notes = "Zero-Waste; cost=0"
        elif name == "RO Water":
            notes = "Filtered/RO water; nominal cost"

        e = ext.get(name, ("", "", "", "", "", "", ""))
        unit, grp_code, cat_code, kcal, prot, fat, carb = e

        schema_code = dish_to_schema.get(data["short_code"], "")

        w.writerow([
            data["short_code"], data["sys_id"], name, data["type"],
            data["orderItemType"], notes, data["std_out"], data["std_uom"],
            data["syrve_sync"],
            unit, grp_code, cat_code, schema_code,
            kcal, prot, fat, carb,
        ])

# ─────────────────────────────────────────────────────────────────────────────
# 2. BOM — helpers & data (unchanged logic, same as v1)
# ─────────────────────────────────────────────────────────────────────────────
yield_dict = {
    "Onion": 0.85, "Fresh Carrot": 0.80, "Raw Beetroot": 0.70,
    "Fresh Potato": 0.75, "Garlic": 0.95,
    "Olive Oil EV": 1.00, "Shishka Mix Spices": 1.00,
    "SF Vegetable Broth Zero-Waste": 1.00, "SF Mirepoix (Saute)": 1.00,
    "SF Baked Beetroot": 1.00, "SF Borsch Base (Vacuum)": 1.00,
    "Lemon Juice": 1.00, "Processing Loss": 1.00,
    "RO Water": 1.00, "Root Trimmings": 1.00, "Onion Trimmings": 1.00,
    "Herb Stems": 1.00, "Mushroom Stems": 1.00, "Cabbage Cores": 1.00,
}

def write_balanced_bom(writer, parent_name, ingredients):
    p_data    = nom[parent_name]
    p_std     = Decimal(str(p_data["std_out"]))
    loss_unit = p_data["std_uom"] if p_data["std_uom"] else "kg"
    net       = Decimal("0")
    for child_name, qty_gross, unit in ingredients:
        y    = Decimal(str(yield_dict.get(child_name, 1.0)))
        net += Decimal(str(qty_gross)) * y
        writer.writerow([p_data["short_code"], parent_name,
                         nom[child_name]["short_code"], child_name, qty_gross, unit])
    loss = float((p_std - net).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    writer.writerow([p_data["short_code"], parent_name,
                     nom["Processing Loss"]["short_code"], "Processing Loss", loss, loss_unit])

with open('BOM.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(["Parent_Code","Parent_Name","Child_Code","Child_Name","QuantityGross","Unit"])

    # L0: SF Vegetable Broth Zero-Waste (10 L batch, scaled from 30 L TTK)
    p = "SF Vegetable Broth Zero-Waste"
    for child_name, qty, unit in [
        ("RO Water",          11.700, "l"),
        ("Root Trimmings",     1.000, "kg"),
        ("Onion Trimmings",    0.667, "kg"),
        ("Herb Stems",         0.167, "kg"),
        ("Mushroom Stems",     0.333, "kg"),
        ("Cabbage Cores",      0.333, "kg"),
        ("Shishka Mix Spices", 0.017, "kg"),
    ]:
        w.writerow([nom[p]["short_code"], p, nom[child_name]["short_code"], child_name, qty, unit])
    w.writerow([nom[p]["short_code"], p,
                nom["Processing Loss"]["short_code"], "Processing Loss", -1.700, "l"])

    # L1: SF Mirepoix — output 1 kg
    write_balanced_bom(w, "SF Mirepoix (Saute)", [
        ("Onion",             "0.606", "kg"),
        ("Fresh Carrot",      "0.606", "kg"),
        ("Olive Oil EV",      "0.121", "l"),
        ("Shishka Mix Spices","0.061", "kg"),
    ])

    # L1: SF Baked Beetroot — output 1 kg
    write_balanced_bom(w, "SF Baked Beetroot", [("Raw Beetroot", "1.764", "kg")])

    # L2: SF Borsch Base — output 10 l
    write_balanced_bom(w, "SF Borsch Base (Vacuum)", [
        ("SF Vegetable Broth Zero-Waste", "7.181", "l"),
        ("SF Mirepoix (Saute)",           "1.026", "kg"),
        ("SF Baked Beetroot",             "1.539", "kg"),
        ("Fresh Potato",                  "1.026", "kg"),
        ("Lemon Juice",                   "0.103", "l"),
        ("Garlic",                        "0.051", "kg"),
    ])

    # L3: Sale Dish — 1 portion = 0.3 l borsch base
    p = "Borsch Bio-Active (portion)"
    w.writerow([nom[p]["short_code"], p,
                nom["SF Borsch Base (Vacuum)"]["short_code"],
                "SF Borsch Base (Vacuum)", "0.3", "l"])

# ─────────────────────────────────────────────────────────────────────────────
# 3. MODIFIER SCHEMES  (now with Schema_Code column)
# ─────────────────────────────────────────────────────────────────────────────
# Portion_Size_kg lookup: same values as Sale_Ratio in UOM_Mapping for MOD items
mod_portion_kg = {
    "Sous-vide Chicken": "0.08",
    "Red Beans":         "0.04",
    "Sour Cream":        "0.03",
    "Coconut Yogurt":    "0.03",
    "Ancient Crunch":    "0.02",
    "Greens":            "0.005",
}

with open('Modifier_Schemes.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow([
        "Schema_Code",
        "Target_Dish_Code", "Target_Dish_Name",
        "Modifier_Group_Code", "Modifier_Group_Name",
        "MinAmount_Group", "MaxAmount_Group",
        "Modifier_Item_Code", "Modifier_Item_Name",
        "DefaultAmount_Item",
        "Portion_Size_kg",   # v3: serving weight in kg, used for cost calc
    ])
    p      = "Borsch Bio-Active (portion)"
    p_code = nom[p]["short_code"]
    sc     = dish_to_schema.get(p_code, "")

    # modifier rows: (group_name, min, max, item_name, default)
    mod_rows = [
        ("Add-ons (Protein)", "1","1", "Sous-vide Chicken", "1"),
        ("Add-ons (Protein)", "1","1", "Red Beans",         "0"),
        ("Toppings",          "0","3", "Ancient Crunch",    "0"),
        ("Toppings",          "0","3", "Sour Cream",        "0"),
        ("Toppings",          "0","3", "Coconut Yogurt",    "0"),
        ("Toppings",          "0","3", "Greens",            "0"),
    ]
    for (g, mn, mx, item, default) in mod_rows:
        portion_kg = mod_portion_kg.get(item, "0")
        w.writerow([sc, p_code, p, nom[g]["short_code"], g, mn, mx,
                    nom[item]["short_code"], item, default, portion_kg])

# ─────────────────────────────────────────────────────────────────────────────
# 4. PRODUCTION FLOW
# ─────────────────────────────────────────────────────────────────────────────
with open('Production_Flow.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(["Product_Code","Product_Name","Operation","Equipment_ID",
                "Temperature","Duration_Min","Is_Bottleneck","Notes"])

    p = "SF Vegetable Broth Zero-Waste"
    w.writerow([nom[p]["short_code"], p, "Roasting Trimmings",  "L-1-K-EL-CON-OVEN-83", "200","25","No", "Unit 20, 200°C — Maillard reaction"])
    w.writerow([nom[p]["short_code"], p, "Simmering",           "L-1-K-GAS-RNG-570-32",  "95","75","Yes","Unit 32 — bring to boil, bare simmer 60-90 min"])
    w.writerow([nom[p]["short_code"], p, "Straining",           "MANUAL",                "",  "10","No", "Fine sieve/cheesecloth; solids to compost"])
    w.writerow([nom[p]["short_code"], p, "Cooling",             "L-1-K-BL-FRZ-790-66",   "3","45","No", "Unit 66 — Blast Chiller to 3°C"])
    w.writerow([nom[p]["short_code"], p, "Vacuuming",           "L-1-K-VAC-500-67",       "", "10","No", "Unit 67 — 5 L bags; up to 5 days"])

    p = "SF Baked Beetroot"
    w.writerow([nom[p]["short_code"], p, "Baking",  "L-1-K-EL-CON-OVEN-83","180","120","Yes","Unit 20, 180°C"])

    p = "SF Mirepoix (Saute)"
    w.writerow([nom[p]["short_code"], p, "Sauteing","L-1-K-GAS-RNG-570-32","160","15","No","Unit 32"])

    p = "SF Borsch Base (Vacuum)"
    w.writerow([nom[p]["short_code"], p, "Boiling Potato","L-1-K-GAS-RNG-570-32","100","60","No","Unit 32"])
    w.writerow([nom[p]["short_code"], p, "Cooling",       "L-1-K-BL-FRZ-790-66",  "3","45","No","Unit 66"])
    w.writerow([nom[p]["short_code"], p, "Vacuuming",     "L-1-K-VAC-500-67",      "", "10","No","Unit 67"])

# ─────────────────────────────────────────────────────────────────────────────
# 5. UOM MAPPING  (v3 — full coverage for all items)
# ─────────────────────────────────────────────────────────────────────────────
# Columns:
#   Product_Code | Product_Name | Base_UOM | Storage_UOM | Storage_Ratio
#   Sale_UOM | Sale_Ratio
#
# Sale_Ratio semantics:
#   RAW / zero-waste  → 1  (costed per kg/l, same as purchase unit)
#   PF (intermediate) → 1  (costed per l or kg; portion link is via BOM)
#   PF-BORSCH_BASE    → 0.3  (1 portion = 0.3 l of borsch base)
#   MOD items         → portion size in kg  (used in Modifier cost formula)
#   SALE              → 1  (1 portion = 1 portion)
uom_rows = [
    # ── Purchased Raw Ingredients ──────────────────────────────────────────
    ("Fresh Carrot",          "kg",     "Bag 25kg",    "25",  "kg",     "1"),
    ("Onion",                 "kg",     "Bag 25kg",    "25",  "kg",     "1"),
    ("Olive Oil EV",          "l",      "Bottle 1L",   "1",   "l",      "1"),
    ("Raw Beetroot",          "kg",     "Bag 25kg",    "25",  "kg",     "1"),
    ("Fresh Potato",          "kg",     "Bag 25kg",    "25",  "kg",     "1"),
    ("Lemon Juice",           "l",      "Bottle 1L",   "1",   "l",      "1"),
    ("Garlic",                "kg",     "Box 5kg",     "5",   "kg",     "1"),
    ("Shishka Mix Spices",    "kg",     "Pack 500g",   "0.5", "kg",     "1"),
    # ── Zero-Waste Broth Inputs ────────────────────────────────────────────
    ("RO Water",              "l",      "Dispenser",   "20",  "l",      "1"),
    ("Root Trimmings",        "kg",     "GN Tray",     "5",   "kg",     "1"),
    ("Onion Trimmings",       "kg",     "GN Tray",     "5",   "kg",     "1"),
    ("Herb Stems",            "kg",     "GN Tray",     "2",   "kg",     "1"),
    ("Mushroom Stems",        "kg",     "GN Tray",     "3",   "kg",     "1"),
    ("Cabbage Cores",         "kg",     "GN Tray",     "5",   "kg",     "1"),
    # ── Semi-Finished ──────────────────────────────────────────────────────
    ("SF Vegetable Broth Zero-Waste", "l",  "Bag 5L",  "5",   "l",      "1"),
    ("SF Mirepoix (Saute)",           "kg", "GN 1/1",  "3",   "kg",     "1"),
    ("SF Baked Beetroot",             "kg", "GN 1/1",  "3",   "kg",     "1"),
    ("SF Borsch Base (Vacuum)",       "l",  "Bag 1.5L","1.5", "portion","0.3"),
    # ── Modifiers — Sale_Ratio = serving size in kg ────────────────────────
    # These are the default portion weights used in cost calc
    ("Sous-vide Chicken",  "kg", "Pack 100g",   "0.1", "portion", "0.08"),
    ("Red Beans",          "kg", "Can 400g",    "0.4", "portion", "0.04"),
    ("Sour Cream",         "kg", "Bucket 1kg",  "1",   "portion", "0.03"),
    ("Coconut Yogurt",     "kg", "Bucket 1kg",  "1",   "portion", "0.03"),
    ("Ancient Crunch",     "kg", "Bag 200g",    "0.2", "portion", "0.02"),
    ("Greens",             "kg", "Bunch 100g",  "0.1", "portion", "0.005"),
    # ── Sale Dish ──────────────────────────────────────────────────────────
    ("Borsch Bio-Active (portion)", "portion", "Bowl", "1", "portion", "1"),
]

with open('UOM_Mapping.tsv', 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(["Product_Code","Product_Name","Base_UOM","Storage_UOM","Storage_Ratio","Sale_UOM","Sale_Ratio"])
    for (name, base_uom, stor_uom, stor_ratio, sale_uom, sale_ratio) in uom_rows:
        code = nom[name]["short_code"]
        w.writerow([code, name, base_uom, stor_uom, stor_ratio, sale_uom, sale_ratio])

print("✅  TSVs v3 generated:")
print("   + Groups.tsv")
print("   + Product_Categories.tsv")
print("   + Modifier_Schema_Registry.tsv")
print("   Nomenclature: +measureUnit, +groupId, +productCategoryId, +modifierSchemaId, +nutrition")
print("   Modifier_Schemes: +Schema_Code, +Portion_Size_kg")
print(f"   UOM_Mapping: {len(uom_rows)} items (full coverage)")
