# CommerceFlow — Roadmap (B2B / pilot-ready)

**Status:** MVP demo → pilot-ready SaaS  
**Updated:** 2026-06-01

---

## Trenutno stanje (v1.1)

| Aspekt | Ocjena | Napomena |
|--------|--------|----------|
| Analitički motor | 8/10 | Profit, inventory, product intel, Excel + PDF export |
| UI / landing | 7/10 | Profesionalan demo |
| B2B readiness | 6/10 | Auth, org isolation, team invites, live store sync |
| Security | 6/10 | Admin zaštita, upload rate limit, encrypted store tokens |
| Enterprise appeal | 7/10 | Shopify/WooCommerce OAuth + scheduled reports |

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
- [x] Team invite + role (Owner / Analyst / Viewer)

---

## Faza 2 — Produkcija & stabilnost (sedmica 3–4)

- [x] PostgreSQL podrška u kodu (`postgresql+asyncpg`, migracije, Render `render.yaml`)
- [x] PostgreSQL instanca na Renderu + `DATABASE_URL` (ručno — korisnik postavio Basic)
- [x] Dnevni backup baze (Render Postgres Basic + `/api/admin/backup-status`)
- [x] SMTP na Renderu (feedback + registracija + weekly report email)
- [x] Više API/integration testova (`tests/test_phase2_phase3.py`)
- [x] Rate limit na upload (IP sliding window)

---

## Faza 3 — Pilot-ready features (sedmice 5–8)

- [x] **Shopify OAuth connect** (read-only: products, orders, inventory)
- [x] **Scheduled weekly Excel report** (email cron endpoint + UI schedule)
- [x] **PDF executive summary** export
- [x] WooCommerce REST sync (read-only)
- [x] Team invite (2–5 seats po organizaciji)
- [x] Role: Owner / Analyst / Viewer

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
1. Admin API zaštita          ← Faza 0 (kod) ✅
2. Login + org isolation      ← Faza 1 (kod) ✅
3. PostgreSQL                 ← Faza 2 ✅
4. Shopify connect            ← Faza 3 ✅
5. Scheduled reports          ← Faza 3 ✅
6. Stripe + team              ← Faza 4
```

---

## Progress log

| Datum | Šta urađeno |
|-------|-------------|
| 2026-06-01 | ROADMAP kreiran; Faza 0 admin zaštita; Faza 1 auth MVP |
| 2026-06-01 | Faza 2: SMTP, upload rate limit, backup status API, testovi |
| 2026-06-01 | Faza 3: Shopify/WooCommerce sync, PDF export, weekly reports, team invites |
