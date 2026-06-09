# CommerceFlow — Roadmap (B2B / pilot-ready)

**Status:** MVP demo → pilot-ready SaaS  
**Updated:** 2026-06-01

---

## Trenutno stanje (v1.0)

| Aspekt | Ocjena | Napomena |
|--------|--------|----------|
| Analitički motor | 8/10 | Profit, inventory, product intel, Excel export |
| UI / landing | 7/10 | Profesionalan demo |
| B2B readiness | 3/10 | Nema auth, tenant isolation |
| Security | 4/10 | Shared guest workspace, admin rupe |
| Enterprise appeal | 5/10 | File upload only, nema live Shopify |

---

## Faza 0 — Sigurnost & dokumentacija (sedmica 1)

- [x] ROADMAP.md — ovaj dokument
- [x] Zaštititi destructive `/api/admin/*` rute u produkciji (`USAGE_STATS_KEY`)
- [ ] `SECRET_KEY` jak na Renderu (ručno u Environment)
- [ ] Jedan canonical URL (`commerceflow-1.onrender.com`)

---

## Faza 1 — Auth & privatni workspace (sedmice 2–3)

- [x] Email + password registracija
- [x] Login / logout (secure session cookie)
- [x] `Organization` + `User` modeli u upotrebi
- [x] Importi vezani za `organization_id`
- [x] Katalog dataset-a filtriran po organizaciji
- [x] Guest demo i dalje radi bez logina (`organization_id = NULL`)
- [x] Login stranica u dashboardu (`/login`)
- [x] Reset/clear samo za podatke svoje organizacije
- [ ] Team invite + role (Owner / Analyst / Viewer)

---

## Faza 2 — Produkcija & stabilnost (sedmica 3–4)

- [ ] PostgreSQL umjesto SQLite (Render persistent disk ili managed DB)
- [ ] Dnevni backup baze
- [ ] SMTP na Renderu (feedback email obavijesti)
- [ ] Više API/integration testova
- [ ] Rate limit na upload

---

## Faza 3 — Pilot-ready features (sedmice 5–8)

- [ ] **Shopify OAuth connect** (read-only: products, orders, inventory)
- [ ] **Scheduled weekly Excel report** (email cron)
- [ ] **PDF executive summary** export
- [ ] WooCommerce REST sync (read-only)
- [ ] Team invite (2–5 seats po organizaciji)
- [ ] Role: Owner / Analyst / Viewer

---

## Faza 4 — Enterprise appeal (mjesec 3+)

- [ ] Multi-store / multi-brand po organizaciji
- [ ] Custom alert rules (margin < X%, stock < Y dana)
- [ ] Comparison periods (Q1 vs Q2, YoY)
- [ ] SSO (Google / Microsoft)
- [ ] Stripe billing (free / pro / team)
- [ ] Slack / Teams alert webhook
- [ ] GDPR: data export & delete po organizaciji
- [ ] Competitor price tracking (stub već postoji)
- [ ] White-label reports (logo firme na Excel/PDF)

---

## Pilot offer (LinkedIn / outreach)

> **Free 60-day private workspace** for 2 design partners.  
> Import → analyze → executive Excel. No credit card.

---

## Redoslijed implementacije (preporuka)

```
1. Admin API zaštita          ← Faza 0 (kod)
2. Login + org isolation      ← Faza 1 (kod)
3. PostgreSQL                 ← Faza 2
4. Shopify connect            ← Faza 3 (najveći wow)
5. Scheduled reports          ← Faza 3
6. Stripe + team              ← Faza 4
```

---

## Progress log

| Datum | Šta urađeno |
|-------|-------------|
| 2026-06-01 | ROADMAP kreiran; Faza 0 admin zaštita; Faza 1 auth MVP (register/login, org-scoped imports) |
