#!/bin/bash
# Reset the messy_files directory to its starting state for the demo.
# Run this before each demonstration of the file organizer.

set -e

cd "$(dirname "$0")"

# Clean up any existing files
rm -rf messy_files
mkdir messy_files

# Create sample messy files
touch "messy_files/Meeting Notes (2).docx"
touch "messy_files/FINAL_Report_v3.pdf"
touch "messy_files/John's Birthday Photo!!.jpg"
touch "messy_files/2024-03-15 Invoice #1234.pdf"
touch "messy_files/project_proposal___DRAFT.txt"
touch "messy_files/README (copy).md"

echo "Created messy_files/ with sample files:"
ls -1 messy_files/
