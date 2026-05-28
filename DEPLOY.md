# Deploy CommerceFlow (javni link za LinkedIn)

Lokalno (`127.0.0.1`) **samo ti vidiš**. Za LinkedIn treba **javni HTTPS URL**.

## Render.com (~10 minuta)

**Settings → Environment (obavezno):**
- `PYTHON_VERSION` = `3.11.9`
- `SECRET_KEY` = Generate
- `USAGE_STATS_KEY` = tvoja šifra
- `OPENAI_API_KEY` = tvoj ključ (opcionalno)

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
curl -X POST https://TVOJ-URL.onrender.com/api/admin/demo/load/atlas
```

Zatim **Run Analysis** u UI-u.

> Free tier: disk se ponekad resetira — za demo ponovo klikni **Load live demo**.

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
