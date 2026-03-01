import csv

files = [
    ("Nomenclature", "Nomenclature.tsv"),
    ("BOM", "BOM.tsv"),
    ("Modifier_Schemes", "Modifier_Schemes.tsv"),
    ("Production_Flow", "Production_Flow.tsv"),
    ("UOM_Mapping", "UOM_Mapping.tsv")
]

for sheet_name, f_name in files:
    html = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
<table>
"""
    with open(f_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter='\t')
        for idx, row in enumerate(reader):
            html += "  <tr>\n"
            for col in row:
                tag = "th" if idx == 0 else "td"
                html += f"    <{tag}>{col}</{tag}>\n"
            html += "  </tr>\n"
    html += "</table>\n</body></html>"
    
    with open(f"{sheet_name}_table.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated {sheet_name}_table.html")
