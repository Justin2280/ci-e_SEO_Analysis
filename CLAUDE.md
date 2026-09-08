# CI Search Manager — projectinstructies voor Claude Code

Doel: een eigen "AI Search Manager" voor ci-engineers.com (WordPress op Hostinger).
Eigenaar: Justin de Weert (CI-Engineers B.V. / deweert.ai). Taal in code-comments en output: Nederlands.
Justin werkt op **Windows** (PowerShell): instructies daarop richten; code blijft cross-platform (pathlib, geen shell-specifieke calls).

## Context
- CI-Engineers is een civiel ingenieursbureau + detacheringsbureau (15 personen, NL).
- Twee doelgroepen: (1) opdrachtgevers die civiele engineering/gedetacheerde engineers zoeken,
  (2) potentieel personeel (constructeurs, projectleiders, tekenaars) dat een werkgever zoekt.
- Site: WordPress 7 op Hostinger, thema Elementor, SEO-plugin **Yoast SEO** (sitemap op /sitemap_index.xml,
  `yoast_head_json` publiek in de REST API). Koppeling via WP REST API met application password (src/wp_client.py).

## Modules
1. `src/ai_visibility.py` — DONE. Stelt vragen aan OpenAI/Claude/Gemini, logt of CI-Engineers genoemd wordt.
2. `src/seo_audit.py` — DONE. Sitemap-crawl, per pagina title/description/H1/canonical/noindex/JSON-LD/links/alt/woorden/laadtijd.
   Stdlib HTMLParser (geen bs4). Rapport in data/reports/seo_audit-*.md.
3. `src/search_console.py` — DONE. GSC API via service account, laatste 28 dagen (lag 3), dimensies query/page/page+query.
4. `src/wp_client.py` — DONE. Paginering, Yoast/Rank Math-detectie, `seo_meta()`, preview-diff + bevestiging voor schrijven.
   Schrijven vereist `wp/mu-plugins/ci-seo-meta.php` op de server (register_post_meta show_in_rest).
5. `src/report.py` — DONE. Weekrapport uit de nieuwste twee runs per module, trend ▲/▼, optioneel e-mail (smtplib).

Gedeeld: `src/common.py` (ROOT/RESULTS/REPORTS, `save_jsonl`, `load_runs`, `utf8_console`).
JSONL-naamgeving: `data/results/<module>-YYYY-MM-DD.jsonl`; ai_visibility gebruikt het oude `YYYY-MM-DD.jsonl`.
Elke rij heeft `ts` en `module`. Meerdere runs op één dag worden aan hetzelfde bestand toegevoegd (append).

## Regels
- Nooit content op de live site wijzigen zonder expliciete bevestiging; eerst een diff/preview tonen
  (`write_seo_meta(confirm=True)` pas na `JA` in de CLI).
- API-keys alleen via .env (python-dotenv). Nooit hardcoden, nooit committen. Service-account-JSON staat in .gitignore.
- Resultaten als JSONL in data/results/ zodat trends over tijd te plotten zijn.
- Houd het simpel: standaardbibliotheek + requests + officiële SDK's. Geen frameworks tenzij nodig.
- Elke module heeft `--dry-run` zonder API-calls; test daarmee voor je echte calls doet.
- `python -m pytest` moet groen blijven (tests zonder netwerk; pure functies testen, netwerk-wrappers apart houden).
- Console-output: roep `utf8_console()` aan in elke `__main__` (anders crasht ✔/✘ op een Windows-console).

## Ideeën voor later
- Trendgrafieken uit de JSONL (matplotlib) in het weekrapport.
- JobPosting-schema controleren op de werken-bij-pagina's (nu alleen Organization/LocalBusiness).
- Vragen in config/queries.yaml periodiek aanvullen met echte GSC-zoekwoorden.
