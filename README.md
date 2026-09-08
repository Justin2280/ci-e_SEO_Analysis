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
.\setup.ps1          # maakt .venv, installeert alles, maakt .env aan, draait de tests en checkt de .env
```
Daarna alleen nog de keys in `.env` invullen. Controleren wat er nog ontbreekt:
```powershell
.\.venv\Scripts\Activate.ps1
python -m src.common --check-env
python -m src.seo_audit --dry-run      # elke module heeft --dry-run zonder API-calls
```
Lukt een `.ps1` niet (execution policy)? Eenmalig: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Benodigde keys / toegang
| Wat | Waar | Nodig voor |
|---|---|---|
| OPENAI_API_KEY | platform.openai.com → API keys | ChatGPT-vermeldingen |
| ANTHROPIC_API_KEY | console.anthropic.com | Claude-vermeldingen |
| GEMINI_API_KEY | aistudio.google.com → Get API key | Gemini-vermeldingen |
| WP_USERNAME + WP_APP_PASSWORD | WordPress → Gebruikers → Profiel → Application Passwords | SEO-meta schrijven (lezen kan zonder) |
| GSC_SERVICE_ACCOUNT_FILE + GSC_SITE_URL | zie hieronder | Search Console-data |
| MS_TENANT_ID + MS_CLIENT_ID + MS_CLIENT_SECRET (of SMTP_*) + REPORT_EMAIL_* | Microsoft Entra, zie *Rapport mailen* | alleen `python -m src.report --email` |

Modelnamen staan in `.env` (lokaal) of als Variables in GitHub — controleer ze bij de providers als een module
fouten geeft. Voorbeeld: `gemini-2.5-flash` gaf in september 2026 een 404 ("no longer available"), nu `gemini-3.6-flash`.

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
1. ✔ Gedaan: `wp/mu-plugins/ci-seo-meta.php` staat op de server in `public_html/wp-content/mu-plugins/`
   (bij een nieuwe site: uploaden via hPanel → Bestandsbeheer; mu-plugins zijn direct actief).
   `python -m src.wp_client --detect` meldt nu *Metavelden zichtbaar via REST: ja*.
2. Zet `WP_USERNAME` en `WP_APP_PASSWORD` in `.env` (WordPress → Gebruikers → Profiel → Application Passwords).
3. Wijzigen: `python -m src.wp_client --set 1388 --description "Nieuwe tekst"` toont eerst een diff en schrijft pas na `JA`.
   Met `--dry-run` wordt er nooit geschreven. Posts i.p.v. pagina's: `--kind posts`.

Let op: een lege `_yoast_wpseo_title` betekent dat Yoast het sjabloon gebruikt ("%%title%% - %%sitename%%", dus
"Contact - CI Engineers"). Een title schrijven overschrijft dat sjabloon voor die pagina; een description schrijven
vult het veld dat nu op veel pagina's leeg is.

## Draaien via GitHub Actions (aanbevolen, niets lokaal nodig)
`.github/workflows/weekly.yml` draait elke maandagochtend alle modules en commit de resultaten (`data/results/`,
`data/reports/`) terug in de repo. Het weekrapport staat dan in `data/reports/weekrapport-YYYY-MM-DD.md` en als
artifact bij de run. Handmatig starten: **Actions → Weekly run → Run workflow**. Een herhaalde run op dezelfde dag
vervangt de resultaten van die dag (dus geen dubbele cijfers in het rapport).

Eenmalig instellen in GitHub → **Settings → Secrets and variables → Actions → Repository secrets**:

| Secret | Inhoud |
|---|---|
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | API-keys; weglaten = provider overslaan |
| `GSC_SERVICE_ACCOUNT_JSON` (of `GSC_SERVICE_ACCOUNT_FILE`) | de **volledige inhoud** van het service-account-JSON-bestand (open het in Kladblok, alles kopiëren) |
| `GSC_SITE_URL` | optioneel; als secret of variable, standaard `sc-domain:ci-engineers.com` |
| `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `REPORT_EMAIL_FROM`, `REPORT_EMAIL_TO` | rapport mailen via Microsoft 365, zie *Rapport mailen* hieronder |

Optioneel onder het tabblad **Variables**: `OPENAI_MODEL`,
`ANTHROPIC_MODEL`, `GEMINI_MODEL`, `SMTP_PORT`.

Let op: de resultaten (AI-antwoorden, GSC-cijfers) komen in de repo te staan; houd de repo dus privé.
De WordPress-inloggegevens zijn hier niet nodig: SEO-teksten schrijven blijft een handmatige actie met bevestiging.
`.github/workflows/tests.yml` draait bij elke push en PR de tests en dry-runs.

### Rapport mailen via Microsoft 365 / Exchange Online
Het rapport wordt verstuurd vanuit een bestaande mailbox via de Microsoft Graph API. Daar is **geen DNS-wijziging**
voor nodig (SPF/DKIM/DMARC staan al goed voor Exchange). Wel een eenmalige app-registratie, door een beheerder van
jullie Microsoft 365-tenant:

1. Ga naar [entra.microsoft.com](https://entra.microsoft.com) → **App-registraties → Nieuwe registratie**.
   Naam: `CI Search Manager`, accounttype: *alleen deze organisatie*, geen redirect-URI. Registreren.
2. Noteer op de overzichtspagina **Toepassings-id (client)** → secret `MS_CLIENT_ID` en **Map-id (tenant)** → `MS_TENANT_ID`.
3. **Certificaten en geheimen → Nieuw clientgeheim** (bijv. 24 maanden). Kopieer direct de *Waarde* (niet de id) → `MS_CLIENT_SECRET`.
   Zet een herinnering voor de vervaldatum; daarna een nieuw geheim aanmaken en het secret in GitHub vervangen.
4. **API-machtigingen → Machtiging toevoegen → Microsoft Graph → Toepassingsmachtigingen → `Mail.Send`** →
   toevoegen → **Beheerderstoestemming verlenen**.
5. In GitHub de secrets `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `REPORT_EMAIL_FROM` (de afzender-mailbox,
   bijv. `info@ci-engineers.com`) en `REPORT_EMAIL_TO` (ontvangers, komma-gescheiden) invoeren.
6. Test: **Actions → Weekly run → Run workflow** met "Rapport ook mailen" aangevinkt.

Aanbevolen (beveiliging): `Mail.Send` als toepassingsmachtiging mag standaard vanuit élke mailbox versturen. Beperk dat
tot de afzender-mailbox met een *application access policy* in Exchange Online PowerShell:
```powershell
Connect-ExchangeOnline
New-ApplicationAccessPolicy -AppId "<MS_CLIENT_ID>" -PolicyScopeGroupId info@ci-engineers.com -AccessRight RestrictAccess -Description "CI Search Manager mag alleen vanuit info@ mailen"
```
(Werkt ook met een mail-enabled beveiligingsgroep als scope.)

Alternatief zonder app-registratie: klassiek SMTP (`SMTP_HOST=smtp.office365.com`, `SMTP_USER`/`SMTP_PASSWORD` van de
mailbox, *Geverifieerde SMTP* aan in het Microsoft 365-beheercentrum bij die gebruiker). Microsoft schakelt basic-auth
SMTP eind december 2026 standaard uit; de Graph-route is daarom de duurzame keuze.

## Wekelijks draaien op je eigen pc (alternatief, Taakplanner)
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
data/results/           JSONL per run (door de workflow gecommit)
data/reports/           markdown-rapporten (door de workflow gecommit)
.github/workflows/      weekly.yml (wekelijkse run) en tests.yml (pytest + dry-runs)
setup.ps1               eenmalige installatie (venv, .env, tests)
run_weekly.ps1          alles achter elkaar draaien (Taakplanner)
```
