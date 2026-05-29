export const LINKS = {
  github: "https://github.com/a-sehic-dev",
  repo: "https://github.com/a-sehic-dev/-CommerceFlow",
  linkedin: "https://www.linkedin.com/in/sedin-sehic-1134253a8/",
  youtube: "https://www.youtube.com/embed/UUou-nnGXnU",
  youtubeWatch: "https://youtu.be/UUou-nnGXnU",
  email: "commerceflow.platform@gmail.com",
  demo: "/dashboard",
} as const;

/** Latest ChronoHaus Watch Co. demo snapshot for landing preview. */
export const PREVIEW_ANALYTICS = {
  revenue: "$3.2M",
  grossMargin: "42.4%",
  inventoryEfficiency: "70.8%",
  riskScore: "72.4",
  deadInventory: "$0",
  ordersAnalyzed: "4,500",
  activeProducts: "120",
  operationalAlerts: "350",
  revenueTrendBars: [47, 53, 51, 20, 63, 51, 33, 66, 22, 29, 40, 20],
  categoryMix: [
    { label: "Pilot", pct: 22 },
    { label: "Sport", pct: 21 },
    { label: "Dress", pct: 21 },
    { label: "Dive", pct: 19 },
    { label: "Smart Hybrid", pct: 17 },
  ],
  inventoryRisk: [
    { label: "Low", pct: 9 },
    { label: "Medium", pct: 137 },
    { label: "Critical", pct: 0 },
  ],
} as const;

export const TRUST_TAGS = [
  "CSV/XLSX Imports",
  "Inventory Intelligence",
  "Executive Dashboards",
  "Profit Leakage Detection",
  "Operational Analytics",
  "Stress-tested with 100k+ operational records.",
  "Built by Sedin Šehić",
] as const;

export const FOUNDER_BADGES = [
  "Bosnia & Herzegovina",
  "Bosnian",
  "English",
  "German",
  "Economics & Business Operations",
  "Python",
  "FastAPI",
  "Operational Analytics",
  "Data Pipelines",
] as const;

export const FAQ_ITEMS = [
  {
    q: "Is CommerceFlow AI-based?",
    a: "CommerceFlow primarily uses deterministic analytics engines and operational logic instead of black-box AI systems.",
  },
  {
    q: "Can businesses upload their own datasets?",
    a: "Yes. CSV/XLSX operational exports are supported.",
  },
  {
    q: "Can this work with Shopify or WooCommerce exports?",
    a: "Yes. The import engine is designed around ecommerce operational exports and structured spreadsheet workflows.",
  },
  {
    q: "How are operational risk scores calculated?",
    a: "CommerceFlow combines deterministic signals such as inventory aging, stock levels, margin pressure, sales velocity, and anomaly severity into transparent operational scores. The goal is to highlight business risk without relying on opaque black-box logic.",
  },
  {
    q: "Does CommerceFlow support enterprise-scale datasets?",
    a: "CommerceFlow is designed around structured CSV/XLSX workflows with chunked imports, dataset selection, analytics caching, and export limits that support larger operational files while keeping the dashboard responsive.",
  },
] as const;

export const FEATURES = [
  {
    title: "Inventory Intelligence",
    desc: "Low stock, overstock, dead inventory, and reorder insights from your operational exports.",
  },
  {
    title: "Profit Leakage Detection",
    desc: "Surface pricing anomalies, discount exposure, and margin risks before they compound.",
  },
  {
    title: "Executive Dashboards",
    desc: "Revenue, operations, inventory health, and KPI rollups in one decision-ready view.",
  },
  {
    title: "CSV/XLSX Import Engine",
    desc: "Import exports from Shopify, WooCommerce, or generic spreadsheets — schema-aware mapping.",
  },
  {
    title: "Alerts & Recommendations",
    desc: "Severity-scored operational warnings and actionable business signals.",
  },
  {
    title: "Enterprise Reporting",
    desc: "Structured Excel workbooks with executive KPIs, charts, and audit-ready traces.",
  },
] as const;
