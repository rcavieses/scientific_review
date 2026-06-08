import csv
import re

input_file = "articulos_paywall_canonicos.csv"
output_file = "articulos_paywall_canonicos_fixed.csv"

# Read the CSV and fix line breaks in titles
rows = []
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 2:
            # Clean the title: remove extra whitespace and newlines
            title = row[1]
            # Replace newlines and multiple spaces with a single space
            title = re.sub(r'\s+', ' ', title).strip()
            row[1] = title
        rows.append(row)

# Write the corrected CSV
with open(output_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print(f"✓ Fixed CSV written to {output_file}")
print(f"✓ Total rows: {len(rows)}")
