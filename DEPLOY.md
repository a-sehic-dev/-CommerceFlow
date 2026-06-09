# Deploy CommerceFlow (javni link za LinkedIn)

Lokalno (`127.0.0.1`) **samo ti vidiš**. Za LinkedIn treba **javni HTTPS URL**.

## Render.com (~10 minuta)

**Settings → Environment (obavezno):**
- `PYTHON_VERSION` = `3.11.9`
- `SECRET_KEY` = Generate
- `USAGE_STATS_KEY` = tvoja šifra (npr. `cf-insights-sedin-2026`) — **isti na svakom Render servisu**
- `OPENAI_API_KEY` = tvoj ključ (opcionalno)

**Jedan javni URL:** Ako imaš više Render servisa (`commerceflow-1`, `commerceflow-svfv`), svaki ima **svoju bazu**. Demo + admin moraju biti **isti hostname**, npr. samo `https://commerceflow-1.onrender.com`.

## Faza 2 — PostgreSQL (preporučeno za produkciju)

SQLite na Renderu **gubi podatke** na redeploy. PostgreSQL ih čuva (nalozi, importi, insights).

### Koraci na Renderu (~5 min)

1. **Dashboard → New + → PostgreSQL** (Free)
2. Ime npr. `commerceflow-db` → **Create Database**
3. Otvori **-CommerceFlow-1** web servis → **Environment**
4. **Add Environment Variable:**
   - Key: `DATABASE_URL`
   - Value: kopiraj **Internal Database URL** iz Postgres servisa (počinje sa `postgres://...`)
5. **Manual Deploy** web servisa (povuče novi kod + `asyncpg`)
6. Founder admin → **database backend: postgresql** (u health panelu)

Lokalno ostaje SQLite — nema promjene za `python run.py`.

> Napomena: Render Postgres free tier ističe nakon 90 dana — za ozbiljan pilot pređi na paid plan ili backup.

**Build Command:**
```
pip install --upgrade pip setuptools wheel && pip install --prefer-binary -r requirements.txt && cd landing && npm ci && npm run build
```

**Start Command:**
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Ako build padne: **Manual Deploy → Clear build cache & deploy**.

## Render.com (stari skraćeni koraci)

1. Push kod na GitHub: https://github.com/a-sehic-dev/-CommerceFlow
2. [render.com](https://render.com) → Sign up → **New +** → **Web Service**
3. Connect GitHub repo `-CommerceFlow`
4. Render detektuje `render.yaml` automatski
5. **Create Web Service** → čekaj build (~3–5 min)
6. URL će biti npr. `https://commerceflow-xxxx.onrender.com`

### Nakon deploya (jednom)

Otvori svoj URL → **Load live demo** (gumb na dashboardu) ili:

```bash
Atlas demo se **automatski učitava** pri startu servera (`AUTO_BOOTSTRAP_DEMO=true`, default).

Ručno (ako treba): `curl -X POST https://TVOJ-URL.onrender.com/api/admin/demo/bootstrap`
```

Zatim **Run Analysis** u UI-u.

> Free tier: disk se ponekad resetira — za demo ponovo klikni **Load live demo**.

## Founder admin (posjeti + feedback)

Jedan privatni link (isti ključ kao `USAGE_STATS_KEY` na Renderu):

`https://TVOJ-URL.onrender.com/admin/insights?key=TVOJ_USAGE_STATS_KEY`

Vidiš:
- **Unique sessions**, landing, page views, Run analysis, export
- **Recent activity** — tko je što uradio (anonimni session id)
- **Feedback inbox** — svi komentari + email iz forme

**Feedback ne stiže automatski na Gmail** osim ako postaviš SMTP na Renderu (`SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`). Inače je samo u admin inboxu.

**Napomena:** Render bez persistent diska briše SQLite na redeploy — stari feedback može nestati.

## Usage insights (bez Google Analytics)

U Render **Environment** dodaj npr.:

`USAGE_STATS_KEY=neki-dugacak-tajni-string`

Otvori (samo ti, s tim ključem):

`https://TVOJ-URL.onrender.com/admin/insights?key=neki-dugacak-tajni-string`

Vidiš: landing posjete, demo load, Run Analysis uspjeh, export, feedback — sve u tvojoj SQLite bazi.

## LinkedIn

U postu stavi **Render URL**, ne `127.0.0.1`.

Primjer:
> Try the live demo: https://commerceflow-xxxx.onrender.com  
> Founder-built · import → analyze → executive Excel

## Lokalno (večeras)

```powershell
$proj = (Get-ChildItem "$env:USERPROFILE\Desktop" | Where-Object { $_.Name -match 'CommerceFlow' }).FullName
Set-Location $proj
.\.venv\Scripts\python.exe run.py
```

Browser: **http://127.0.0.1:8000**
