import uuid
import csv
from decimal import Decimal, ROUND_HALF_UP

NAMESPACE = uuid.UUID('12345678-1234-5678-1234-567812345678')

def generate_uuid(name):
    return str(uuid.uuid5(NAMESPACE, name))

# ─────────────────────────────────────────────────────────────────────────────
# 1. NOMENCLATURE
# Tuple: (Name, Type, OrderItemType, Standard_Output, Standard_Output_UOM, Prefix, Syrve_Sync)
# Standard_Output_UOM clarifies the unit of the batch output (l, kg, portion, "")
# Syrve_Sync: "Yes" = push to Syrve API, "No" = internal accounting only
# ─────────────────────────────────────────────────────────────────────────────
items = [
    # ── Raw Ingredients ──────────────────────────────────────────────────────
    ("Fresh Carrot",          "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Onion",                 "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Olive Oil EV",          "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Raw Beetroot",          "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Fresh Potato",          "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Lemon Juice",           "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Garlic",                "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Shishka Mix Spices",    "good",           "Product",  "",   "",        "RAW",  "Yes"),

    # ── Zero-Waste Broth Ingredients (internal; cost = 0) ────────────────────
    ("RO Water",              "good",           "Product",  "",   "",        "RAW",  "Yes"),
    ("Root Trimmings",        "good",           "Product",  "",   "",        "RAW",  "Yes"),  # carrot/celery offcuts
    ("Onion Trimmings",       "good",           "Product",  "",   "",        "RAW",  "Yes"),  # outer layers / bases
    ("Herb Stems",            "good",           "Product",  "",   "",        "RAW",  "Yes"),  # cilantro/parsley/dill
    ("Mushroom Stems",        "good",           "Product",  "",   "",        "RAW",  "Yes"),  # champignon / lion's mane
    ("Cabbage Cores",         "good",           "Product",  "",   "",        "RAW",  "Yes"),  # cauliflower/broccoli cores

    # ── Semi-Finished (PF) ───────────────────────────────────────────────────
    ("SF Vegetable Broth Zero-Waste", "dish",   "Product",  "10", "l",       "PF",   "Yes"),
    ("SF Mirepoix (Saute)",           "dish",   "Product",  "1",  "kg",      "PF",   "Yes"),
    ("SF Baked Beetroot",             "dish",   "Product",  "1",  "kg",      "PF",   "Yes"),
    ("SF Borsch Base (Vacuum)",       "dish",   "Product",  "10", "l",       "PF",   "Yes"),

    # ── Modifiers & Groups ───────────────────────────────────────────────────
    ("Sous-vide Chicken",     "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Red Beans",             "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Sour Cream",            "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Coconut Yogurt",        "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Ancient Crunch",        "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Greens",                "modifier",       "Product",  "",   "",        "MOD",  "Yes"),
    ("Add-ons (Protein)",     "modifier_group", "",         "",   "",        "MOD",  "Yes"),
    ("Toppings",              "modifier_group", "",         "",   "",        "MOD",  "Yes"),

    # ── Sales Dishes ─────────────────────────────────────────────────────────
    ("Borsch Bio-Active (portion)", "dish",     "Compound", "1",  "portion", "SALE", "Yes"),

    # ── Internal Accounting (NOT synced to Syrve) ────────────────────────────
    ("Processing Loss",       "service",        "",         "",   "",        "LOSS", "No"),
]

def make_short_code(name, prefix):
    clean = "".join(c for c in name if c.isalnum() or c.isspace()).upper()
    parts = clean.split()
    if prefix == "PF" and parts[0] == "SF":
        parts = parts[1:]
    code = "_".join(parts[:2])
    return f"{prefix}-{code}"

nom = {name: {
    "sys_id":      generate_uuid(name) if name != "Processing Loss" else "LOSS-001",
    "short_code":  make_short_code(name, prefix),
    "type":        t,
    "orderItemType": oit,
    "std_out":     std,
    "std_uom":     std_uom,
    "syrve_sync":  syrve_sync,
} for name, t, oit, std, std_uom, prefix, syrve_sync in items}

# ── API Mapping Table ─────────────────────────────────────────────────────────
with open('API_Mapping_Table.tsv', 'w', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow(["Short_Code", "Syrve_System_ID", "Item_Name"])
    for name, data in nom.items():
        writer.writerow([data["short_code"], data["sys_id"], name])

# ── Nomenclature.tsv (now includes Standard_Output_UOM and Syrve_Sync) ────────
with open('Nomenclature.tsv', 'w', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow([
        "Short_Code", "Syrve_System_ID", "Name", "Type", "OrderItemType",
        "UsageNotes", "Standard_Output_Amount", "Standard_Output_UOM", "Syrve_Sync"
    ])
    for name, data in nom.items():
        notes = "Universal SF" if name in ["SF Mirepoix (Saute)", "SF Baked Beetroot"] else ""
        if name in ["Root Trimmings", "Onion Trimmings", "Herb Stems", "Mushroom Stems", "Cabbage Cores"]:
            notes = "Zero-Waste; cost=0"
        elif name == "RO Water":
            notes = "Filtered/RO water; nominal cost"
        writer.writerow([
            data["short_code"], data["sys_id"], name, data["type"],
            data["orderItemType"], notes, data["std_out"],
            data["std_uom"], data["syrve_sync"]
        ])

# ─────────────────────────────────────────────────────────────────────────────
# 2. BOM
# ─────────────────────────────────────────────────────────────────────────────
yield_dict = {
    "Onion":                          0.85,
    "Fresh Carrot":                   0.80,
    "Raw Beetroot":                   0.70,
    "Fresh Potato":                   0.75,
    "Garlic":                         0.95,
    "Olive Oil EV":                   1.00,
    "Shishka Mix Spices":             1.00,
    "SF Vegetable Broth Zero-Waste":  1.00,
    "SF Mirepoix (Saute)":            1.00,
    "SF Baked Beetroot":              1.00,
    "SF Borsch Base (Vacuum)":        1.00,
    "Lemon Juice":                    1.00,
    "Processing Loss":                1.00,
    # Zero-waste broth items (yield irrelevant — they're consumed for flavour)
    "RO Water":                       1.00,
    "Root Trimmings":                 1.00,
    "Onion Trimmings":                1.00,
    "Herb Stems":                     1.00,
    "Mushroom Stems":                 1.00,
    "Cabbage Cores":                  1.00,
}

def write_balanced_bom(writer, parent_name, ingredients):
    """
    Writes BOM rows for all non-loss ingredients, then appends a
    Processing Loss row that makes net-input == Standard_Output_Amount.
    The loss unit is taken from the parent's Standard_Output_UOM so that
    liquid outputs (l) and solid outputs (kg) are handled correctly.
    """
    p_data = nom[parent_name]
    p_std  = Decimal(str(p_data["std_out"]))
    # Loss unit follows the parent's output measurement unit
    loss_unit = p_data["std_uom"] if p_data["std_uom"] else "kg"

    current_net_sum = Decimal("0")
    for child_name, qty_gross, unit in ingredients:
        y = Decimal(str(yield_dict.get(child_name, 1.0)))
        current_net_sum += Decimal(str(qty_gross)) * y
        writer.writerow([
            p_data["short_code"], parent_name,
            nom[child_name]["short_code"], child_name,
            qty_gross, unit
        ])

    loss_needed  = p_std - current_net_sum
    loss_rounded = float(loss_needed.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    writer.writerow([
        p_data["short_code"], parent_name,
        nom["Processing Loss"]["short_code"], "Processing Loss",
        loss_rounded, loss_unit
    ])

with open('BOM.tsv', 'w', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow(["Parent_Code", "Parent_Name", "Child_Code", "Child_Name", "QuantityGross", "Unit"])

    # ── L0: SF Vegetable Broth Zero-Waste (10 L batch, scaled from 30 L recipe) ──
    # Inputs: RO water (main liquid) + zero-waste vegetable trimmings
    # Balance: water input 11.7 L → 10 L output; evaporation loss = -1.7 L
    # Note: solid trimmings (kg) are consumed for flavour extraction;
    #       the liquid balance tracks only water evaporation.
    p = "SF Vegetable Broth Zero-Waste"
    for child_name, qty, unit in [
        ("RO Water",         11.700, "l"),
        ("Root Trimmings",    1.000, "kg"),   # carrot/celery offcuts
        ("Onion Trimmings",   0.667, "kg"),   # outer layers, bases
        ("Herb Stems",        0.167, "kg"),   # cilantro, parsley, dill
        ("Mushroom Stems",    0.333, "kg"),   # champignon / lion's mane
        ("Cabbage Cores",     0.333, "kg"),   # cauliflower, broccoli, kimchi pineapple
        ("Shishka Mix Spices",0.017, "kg"),   # peppercorns, bay leaf
    ]:
        writer.writerow([nom[p]["short_code"], p, nom[child_name]["short_code"], child_name, qty, unit])
    # Evaporation loss (11.7 L water → 10 L broth = 1.7 L lost during simmering)
    writer.writerow([nom[p]["short_code"], p, nom["Processing Loss"]["short_code"],
                     "Processing Loss", -1.700, "l"])

    # ── L1: SF Mirepoix (Saute) — output: 1 kg ───────────────────────────────
    write_balanced_bom(writer, "SF Mirepoix (Saute)", [
        ("Onion",             "0.606", "kg"),
        ("Fresh Carrot",      "0.606", "kg"),
        ("Olive Oil EV",      "0.121", "l"),
        ("Shishka Mix Spices","0.061", "kg"),
    ])

    # ── L1: SF Baked Beetroot — output: 1 kg ─────────────────────────────────
    write_balanced_bom(writer, "SF Baked Beetroot", [
        ("Raw Beetroot", "1.764", "kg"),
    ])

    # ── L2: SF Borsch Base (Vacuum) — output: 10 l ───────────────────────────
    write_balanced_bom(writer, "SF Borsch Base (Vacuum)", [
        ("SF Vegetable Broth Zero-Waste", "7.181", "l"),
        ("SF Mirepoix (Saute)",           "1.026", "kg"),
        ("SF Baked Beetroot",             "1.539", "kg"),
        ("Fresh Potato",                  "1.026", "kg"),
        ("Lemon Juice",                   "0.103", "l"),
        ("Garlic",                        "0.051", "kg"),
    ])

    # ── L3: Sales Dish — 1 portion = 0.3 l of Borsch Base ────────────────────
    p = "Borsch Bio-Active (portion)"
    writer.writerow([nom[p]["short_code"], p,
                     nom["SF Borsch Base (Vacuum)"]["short_code"],
                     "SF Borsch Base (Vacuum)", "0.3", "l"])

# ─────────────────────────────────────────────────────────────────────────────
# 3. MODIFIER SCHEMES
# ─────────────────────────────────────────────────────────────────────────────
with open('Modifier_Schemes.tsv', 'w', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow([
        "Target_Dish_Code", "Target_Dish_Name",
        "Modifier_Group_Code", "Modifier_Group_Name",
        "MinAmount_Group", "MaxAmount_Group",
        "Modifier_Item_Code", "Modifier_Item_Name", "DefaultAmount_Item"
    ])
    p      = "Borsch Bio-Active (portion)"
    p_code = nom[p]["short_code"]

    g = "Add-ons (Protein)"
    writer.writerow([p_code, p, nom[g]["short_code"], g, "1", "1", nom["Sous-vide Chicken"]["short_code"], "Sous-vide Chicken", "1"])
    writer.writerow([p_code, p, nom[g]["short_code"], g, "1", "1", nom["Red Beans"]["short_code"],         "Red Beans",         "0"])

    g = "Toppings"
    writer.writerow([p_code, p, nom[g]["short_code"], g, "0", "3", nom["Ancient Crunch"]["short_code"],  "Ancient Crunch",  "0"])
    writer.writerow([p_code, p, nom[g]["short_code"], g, "0", "3", nom["Sour Cream"]["short_code"],      "Sour Cream",      "0"])
    writer.writerow([p_code, p, nom[g]["short_code"], g, "0", "3", nom["Coconut Yogurt"]["short_code"],  "Coconut Yogurt",  "0"])
    writer.writerow([p_code, p, nom[g]["short_code"], g, "0", "3", nom["Greens"]["short_code"],          "Greens",          "0"])

# ─────────────────────────────────────────────────────────────────────────────
# 4. PRODUCTION FLOW
# Equipment IDs:
#   L-1-K-EL-CON-OVEN-83  → Convection Oven (Unit 20)
#   L-1-K-GAS-RNG-570-32  → Gas Range (Unit 32)
#   L-1-K-BL-FRZ-790-66   → Blast Chiller (Unit 66)
#   L-1-K-VAC-500-67       → Vacuum Sealer (Unit 67)
#   MANUAL                 → No equipment; manual step
# ─────────────────────────────────────────────────────────────────────────────
with open('Production_Flow.tsv', 'w', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow([
        "Product_Code", "Product_Name", "Operation",
        "Equipment_ID", "Temperature", "Duration_Min",
        "Is_Bottleneck", "Notes"
    ])

    # SF Vegetable Broth Zero-Waste (5 steps per chef description)
    p = "SF Vegetable Broth Zero-Waste"
    writer.writerow([nom[p]["short_code"], p, "Roasting Trimmings",
                     "L-1-K-EL-CON-OVEN-83", "200", "25", "No",
                     "Unit 20, 200C — Maillard reaction for depth/colour"])
    writer.writerow([nom[p]["short_code"], p, "Simmering",
                     "L-1-K-GAS-RNG-570-32", "95", "75", "Yes",
                     "Unit 32 — bring to boil, reduce to bare simmer 60-90 min"])
    writer.writerow([nom[p]["short_code"], p, "Straining",
                     "MANUAL", "", "10", "No",
                     "Fine sieve / cheesecloth; solids to compost (Zero-Waste)"])
    writer.writerow([nom[p]["short_code"], p, "Cooling",
                     "L-1-K-BL-FRZ-790-66", "3", "45", "No",
                     "Unit 66 — Blast Chiller to 3°C"])
    writer.writerow([nom[p]["short_code"], p, "Vacuuming",
                     "L-1-K-VAC-500-67", "", "10", "No",
                     "Unit 67 — 5 L vacuum bags; shelf life up to 5 days"])

    # SF Baked Beetroot
    p = "SF Baked Beetroot"
    writer.writerow([nom[p]["short_code"], p, "Baking",
                     "L-1-K-EL-CON-OVEN-83", "180", "120", "Yes",
                     "Unit 20, 180C — until soft through"])

    # SF Mirepoix (Saute)
    p = "SF Mirepoix (Saute)"
    writer.writerow([nom[p]["short_code"], p, "Sauteing",
                     "L-1-K-GAS-RNG-570-32", "160", "15", "No",
                     "Unit 32 — continuous stirring"])

    # SF Borsch Base (Vacuum)
    p = "SF Borsch Base (Vacuum)"
    writer.writerow([nom[p]["short_code"], p, "Boiling Potato",
                     "L-1-K-GAS-RNG-570-32", "100", "60", "No",
                     "Unit 32 — until potatoes are tender"])
    writer.writerow([nom[p]["short_code"], p, "Cooling",
                     "L-1-K-BL-FRZ-790-66", "3", "45", "No",
                     "Unit 66 — Blast Chiller"])
    writer.writerow([nom[p]["short_code"], p, "Vacuuming",
                     "L-1-K-VAC-500-67", "", "10", "No",
                     "Unit 67"])

# ─────────────────────────────────────────────────────────────────────────────
# 5. UOM MAPPING
# ─────────────────────────────────────────────────────────────────────────────
with open('UOM_Mapping.tsv', 'w', newline='') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow([
        "Product_Code", "Product_Name",
        "Base_UOM", "Storage_UOM", "Storage_Ratio",
        "Sale_UOM",  "Sale_Ratio"
    ])
    p = "SF Vegetable Broth Zero-Waste"
    writer.writerow([nom[p]["short_code"], p, "Liter", "Bag 5L", "5", "Portion", "1"])

    p = "SF Borsch Base (Vacuum)"
    writer.writerow([nom[p]["short_code"], p, "Liter", "Package", "1.5", "Portion", "0.3"])

    p = "Borsch Bio-Active (portion)"
    writer.writerow([nom[p]["short_code"], p, "Portion", "Bowl", "1", "Box", "1"])

print("✅  TSVs generated: Nomenclature (with UOM + Syrve_Sync), BOM (Broth added), "
      "Production_Flow (Broth ops added), Modifier_Schemes, UOM_Mapping.")
