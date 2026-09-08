# CI Search Manager

Eigen alternatief voor de IONOS "AI Search Manager", gebouwd voor ci-engineers.com.
Vijf modules die samen wekelijks laten zien hoe zichtbaar CI-Engineers is bij AI-assistenten en in Google,
en wat er technisch aan de site te verbeteren valt.

| Module | Commando | Wat het doet | Keys nodig |
|---|---|---|---|
| 1 AI-zichtbaarheid | `python -m src.ai_visibility` | Stelt de vragen uit `config/queries.yaml` aan ChatGPT, Claude en Gemini; logt of CI-Engineers en concurrenten genoemd worden | OPENAI/ANTHROPIC/GEMINI |
| 2 SEO-audit | `python -m src.seo_audit` | Crawlt de sitemap, checkt per pagina title, description, H1, schema, links, alt-teksten, laadtijd | geen |
| 3 Search Console | `python -m src.search_console` | Zoekwoorden, posities, klikken en CTR van de laatste 28 dagen | GSC service account |
| 4 WordPress SEO-meta | `python -m src.wp_client --list` | SEO-title/description per pagina lezen; schrijven met preview + bevestiging | WP app password |
| 5 Weekrapport | `python -m src.report` | Combineert 1–3 tot één markdown-rapport met trends; optioneel mailen | SMTP (alleen voor --email) |

Elke module heeft `--dry-run` (geen API-calls) en schrijft JSONL naar `data/results/` zodat trends over tijd te volgen zijn.

## Setup (Windows, PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env        # vul daarna de keys in
python -m pytest                   # 19 tests, geen netwerk
python -m src.ai_visibility --dry-run
python -m src.seo_audit --dry-run
python -m src.search_console --dry-run
python -m src.report --dry-run
```
Lukt `Activate.ps1` niet (execution policy)? Eenmalig: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Benodigde keys / toegang
| Wat | Waar | Nodig voor |
|---|---|---|
| OPENAI_API_KEY | platform.openai.com → API keys | ChatGPT-vermeldingen |
| ANTHROPIC_API_KEY | console.anthropic.com | Claude-vermeldingen |
| GEMINI_API_KEY | aistudio.google.com → Get API key | Gemini-vermeldingen |
| WP_USERNAME + WP_APP_PASSWORD | WordPress → Gebruikers → Profiel → Application Passwords | SEO-meta schrijven (lezen kan zonder) |
| GSC_SERVICE_ACCOUNT_FILE + GSC_SITE_URL | zie hieronder | Search Console-data |
| SMTP_* + REPORT_EMAIL_* | je mailprovider | alleen `python -m src.report --email` |

Modelnamen staan in `.env` — controleer of ze nog actueel zijn bij de providers.

### Google Search Console (module 3)
1. console.cloud.google.com → project aanmaken → **APIs & Services → Enable** → "Google Search Console API".
2. **IAM → Service accounts → Create** → daarna *Keys → Add key → JSON*. Sla het bestand op als `config\gsc-service-account.json` (staat in `.gitignore`).
3. In Search Console: **Instellingen → Gebruikers en rechten → Gebruiker toevoegen** met het e-mailadres van het service account (`...@...iam.gserviceaccount.com`), rol *Volledig* of *Beperkt*.
4. `.env`: `GSC_SERVICE_ACCOUNT_FILE=config/gsc-service-account.json` en `GSC_SITE_URL=sc-domain:ci-engineers.com`
   (domeinproperty) of `https://ci-engineers.com/` (URL-prefix) — exact zoals de property in GSC heet.
5. GSC loopt 2–3 dagen achter; het script vraagt daarom standaard t/m `vandaag - 3` (`--lag`).

### WordPress SEO-meta schrijven (module 4)
De site draait **Yoast SEO**. Lezen werkt direct (Yoast zet `yoast_head_json` in de REST API).
Schrijven kan pas als WordPress de metavelden via REST accepteert:
1. Upload `wp/mu-plugins/ci-seo-meta.php` via hPanel → Bestandsbeheer naar `public_html/wp-content/mu-plugins/`
   (map aanmaken als die ontbreekt; mu-plugins zijn direct actief).
2. `python -m src.wp_client --detect` moet dan melden: *Metavelden schrijfbaar via REST: ja*.
3. Wijzigen: `python -m src.wp_client --set 1388 --description "Nieuwe tekst"` toont eerst een diff en schrijft pas na `JA`.
   Met `--dry-run` wordt er nooit geschreven. Posts i.p.v. pagina's: `--kind posts`.

## Wekelijks draaien (Taakplanner)
`run_weekly.ps1` draait alle modules na elkaar en schrijft het rapport. Eenmalig registreren (pas het pad aan):
```powershell
schtasks /Create /TN "CI Search Manager" /SC WEEKLY /D MON /ST 07:00 `
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\pad\naar\ci-e_SEO_Analysis\run_weekly.ps1"
```
Handmatig: `.\run_weekly.ps1` (voeg `-Email` toe om het rapport te mailen).

## Kosten
De AI-zichtbaarheidscheck doet (aantal vragen × 3 providers) calls per run. Met ~10–15 vragen wekelijks blijft dat op
enkele euro's per maand. De overige modules zijn gratis (publieke site, Search Console API, eigen WordPress).

## Structuur
```
CLAUDE.md               instructies voor Claude Code
config/queries.yaml     vragen voor de AI's + merknamen/concurrenten
src/common.py           gedeelde helpers (paden, JSONL, run-historie, console-encoding)
src/ai_visibility.py    module 1  AI-zichtbaarheidscheck
src/seo_audit.py        module 2  SEO-audit via sitemap
src/search_console.py   module 3  Google Search Console
src/wp_client.py        module 4  WordPress REST + SEO-metavelden
src/report.py           module 5  weekrapport (+ e-mail)
wp/mu-plugins/          PHP-snippet om Yoast/Rank Math-velden via REST schrijfbaar te maken
tests/                  pytest (zonder netwerk), fixtures voor --dry-run
data/results/           JSONL per run (gitignored)
data/reports/           markdown-rapporten (gitignored)
run_weekly.ps1          alles achter elkaar draaien (Taakplanner)
```
