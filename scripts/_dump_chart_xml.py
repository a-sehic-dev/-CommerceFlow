import zipfile
from pathlib import Path

p = Path("data/exports/_chart_v2.xlsx")
z = zipfile.ZipFile(p)
xml = z.read("xl/charts/chart1.xml").decode()
print(xml[:2500])
