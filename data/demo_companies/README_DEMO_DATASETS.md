# CommerceFlow Demo Datasets

**Live import / guest workspace (fast on Render):** **ChronoHaus Watch Co.**

| Dataset | File |
|---------|------|
| **Products** | `watch_products.xlsx` |
| **Inventory** | `watch_inventory.xlsx` |
| **Sales** | `watch_sales_2025.xlsx` |

~120 products · ~4,500 sales (2025).

**Marketing / landing preview KPIs** use `atlas_analytics_snapshot.json` ($42.8M, 100k orders stress-test story) — not loaded into Import History.

## Regenerate

```bash
python scripts/generate_watch_demo.py    # import files
# Atlas snapshot (preview only): restore from repo or regenerate via generate_atlas_demo.py
```
