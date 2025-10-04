#!/usr/bin/env python3
"""
Sanitize test participant CSV by replacing phone area codes with 555.
"""

import csv
import re
import sys
import os

def sanitize_phone(phone):
    """Replace area code with 555."""
    if not phone:
        return phone
    # Match common phone formats: (604) 123-4567, 604-123-4567, 604.123.4567, etc.
    phone = re.sub(r'\(?\d{3}\)?', '(555)', phone, count=1)
    return phone

def sanitize_csv(input_file, output_file):
    """Read CSV, sanitize phone numbers, write to output."""
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames

        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for row in reader:
                # Sanitize phone fields
                if 'phone' in row:
                    row['phone'] = sanitize_phone(row['phone'])
                if 'phone2' in row:
                    row['phone2'] = sanitize_phone(row['phone2'])

                writer.writerow(row)

    print(f"Sanitized CSV written to: {output_file}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python sanitize_csv.py <input_csv> <output_csv>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    sanitize_csv(input_file, output_file)
