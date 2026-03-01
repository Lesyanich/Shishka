import csv

files = [
    ("Nomenclature", "Nomenclature.tsv"),
    ("BOM", "BOM.tsv"),
    ("Modifier_Schemes", "Modifier_Schemes.tsv"),
    ("Production_Flow", "Production_Flow.tsv"),
    ("UOM_Mapping", "UOM_Mapping.tsv")
]

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  table, th, td { border: 1px solid black; border-collapse: collapse; padding: 5px; }
</style>
</head>
<body>
"""

for sheet_name, f_name in files:
    html += f"<h2>{sheet_name}</h2>\n<table id='{sheet_name}'>\n"
    # we generated .txt, but let's read the .txt since they were renamed
    txt_name = f_name.replace(".tsv", ".txt")
    with open(txt_name, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter='\t')
        for i, row in enumerate(reader):
            html += "  <tr>\n"
            for col in row:
                tag = "th" if i == 0 else "td"
                html += f"    <{tag}>{col}</{tag}>\n"
            html += "  </tr>\n"
    html += "</table>\n<br>\n"

html += "</body></html>"

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("index.html generated!")
