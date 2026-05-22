# Deploy CommerceFlow (javni link za LinkedIn)

Lokalno (`127.0.0.1`) **samo ti vidiš**. Za LinkedIn treba **javni HTTPS URL**.

## Render.com (~10 minuta, besplatno)

1. Push kod na GitHub: https://github.com/a-sehic-dev/-CommerceFlow
2. [render.com](https://render.com) → Sign up → **New +** → **Web Service**
3. Connect GitHub repo `-CommerceFlow`
4. Render detektuje `render.yaml` automatski
5. **Create Web Service** → čekaj build (~3–5 min)
6. URL će biti npr. `https://commerceflow-xxxx.onrender.com`

### Nakon deploya (jednom)

Otvori svoj URL → **Load live demo** (gumb na dashboardu) ili:

```bash
curl -X POST https://TVOJ-URL.onrender.com/api/admin/demo/load/apple
```

Zatim **Run Analysis** u UI-u.

> Free tier: disk se ponekad resetira — za demo ponovo klikni **Load live demo**.

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
