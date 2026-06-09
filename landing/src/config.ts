export const LINKS = {
  github: "https://github.com/a-sehic-dev",
  repo: "https://github.com/a-sehic-dev/-CommerceFlow",
  linkedin: "https://www.linkedin.com/in/sedin-sehic-1134253a8/",
  youtube: "https://www.youtube.com/embed/UUou-nnGXnU",
  youtubeWatch: "https://youtu.be/UUou-nnGXnU",
  email: "commerceflow.platform@gmail.com",
  demo: "/dashboard",
  login: "/login",
  register: "/login",
} as const;

/** Latest Atlas Retail Group enterprise stress-test snapshot for landing preview. */
export const PREVIEW_ANALYTICS = {
  revenue: "$42.8M",
  grossMargin: "46.3%",
  inventoryEfficiency: "69.4%",
  riskScore: "88.2",
  deadInventory: "$4.8M",
  ordersAnalyzed: "100,000",
  activeProducts: "3,200",
  operationalAlerts: "1,000",
  revenueTrendBars: [96, 95, 98, 90, 100, 98, 96, 96, 94, 94, 95, 99],
  categoryMix: [
    { label: "Electronics", pct: 46 },
    { label: "Gaming", pct: 13 },
    { label: "Fashion", pct: 11 },
    { label: "Home & Living", pct: 8 },
    { label: "Office", pct: 8 },
    { label: "Smart Home", pct: 8 },
    { label: "Other", pct: 7 },
  ],
  inventoryRisk: [
    { label: "Low", pct: 28 },
    { label: "Medium", pct: 57 },
    { label: "Critical", pct: 15 },
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
