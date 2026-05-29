# CommerceFlow Demo Datasets

Public guest workspace: **ChronoHaus Watch Co.** — medium-size retail demo (fast on Render).

| Dataset | File |
|---------|------|
| **Products** | `watch_products.xlsx` |
| **Inventory** | `watch_inventory.xlsx` |
| **Sales** | `watch_sales_2025.xlsx` |

~120 products · ~180 inventory rows · ~4,500 sales lines (2025).

## Regenerate

```bash
python scripts/generate_watch_demo.py
```

Rebuild landing after snapshot change:

```bash
cd landing && npm run build
```

Legacy Atlas 100k packs were removed — too heavy for shared SQLite hosting.
