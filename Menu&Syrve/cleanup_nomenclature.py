import csv
import os

def cleanup_nomenclature():
    file_path = 'Nomenclature.tsv'
    temp_path = 'Nomenclature_temp.tsv'
    
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    with open(file_path, 'r', encoding='utf-8') as f_in, \
         open(temp_path, 'w', encoding='utf-8', newline='') as f_out:
        
        reader = csv.DictReader(f_in, delimiter='\t')
        writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames, delimiter='\t')
        writer.writeheader()
        
        count = 0
        seen_ids = set()
        
        for row in reader:
            # Rule: Remove rows where Name is exactly the same as Short_Code
            if row['Name'] == row['Short_Code']:
                count += 1
                continue
            
            # Rule: Ensure uniqueness of Syrve_System_ID
            sys_id = row['Syrve_System_ID']
            if sys_id in seen_ids:
                count += 1
                continue
            
            seen_ids.add(sys_id)
            writer.writerow(row)
            
    os.replace(temp_path, file_path)
    print(f"Cleaned up {count} duplicate/invalid rows from Nomenclature.tsv.")

if __name__ == "__main__":
    cleanup_nomenclature()
