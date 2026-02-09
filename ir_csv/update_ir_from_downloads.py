# One-off script: copy downloaded IR CSVs into ir_csv with correct names.
# Usage: python update_ir_from_downloads.py
# Source paths (Feb/Mar):
#   t100sb02_1_20260204_153143427.csv -> 2月.csv
#   t100sb02_1_20260204_153152646.csv -> 3月.csv
import shutil
from pathlib import Path

downloads = Path(r"c:\Users\Ennn0526\Downloads")
ir_csv = Path(__file__).resolve().parent

# 2月 = February, 3月 = March (Unicode to avoid terminal encoding)
targets = [
    ("t100sb02_1_20260204_153143427.csv", "2\u6708.csv"),
    ("t100sb02_1_20260204_153152646.csv", "3\u6708.csv"),
]
for src_name, dest_name in targets:
    src = downloads / src_name
    dest = ir_csv / dest_name
    if not src.exists():
        print(f"Skip (not found): {src}")
        continue
    shutil.copy2(str(src), str(dest))
    print(f"Copied: {dest_name}")
