# CI Search Manager — projectinstructies voor Claude Code

Doel: een eigen "AI Search Manager" voor ci-engineers.com (WordPress op Hostinger).
Eigenaar: Justin de Weert (CI-Engineers B.V. / deweert.ai). Taal in code-comments en output: Nederlands.

## Context
- CI-Engineers is een civiel ingenieursbureau + detacheringsbureau (15 personen, NL).
- Twee doelgroepen: (1) opdrachtgevers die civiele engineering/gedetacheerde engineers zoeken,
  (2) potentieel personeel (constructeurs, projectleiders, tekenaars) dat een werkgever zoekt.
- Site: WordPress op Hostinger. Koppeling via WP REST API met application password (zie src/wp_client.py).

## Modules (bouwvolgorde)
1. `src/ai_visibility.py` — DONE (v1). Stelt vragen aan OpenAI/Claude/Gemini, logt of CI-Engineers genoemd wordt.
2. `src/seo_audit.py` — TODO. Crawl ci-engineers.com (sitemap.xml), check per pagina: title, meta description,
   H1, schema.org (Organization/LocalBusiness/JobPosting), interne links, alt-teksten, laadtijd. Output: markdown-rapport in data/reports/.
3. `src/search_console.py` — TODO. Google Search Console API: zoekwoorden, posities, CTR per pagina (laatste 28 dagen).
4. `src/wp_client.py` — v1 aanwezig. Uitbreiden met: Rank Math/Yoast meta-velden lezen/schrijven.
5. `src/report.py` — TODO. Combineer 1-3 tot één wekelijks rapport (markdown), evt. e-mail.

## Regels
- Nooit content op de live site wijzigen zonder expliciete bevestiging; eerst een diff/preview tonen.
- API-keys alleen via .env (python-dotenv). Nooit hardcoden, nooit committen.
- Resultaten als JSONL in data/results/ zodat trends over tijd te plotten zijn.
- Houd het simpel: standaardbibliotheek + requests + officiële SDK's. Geen frameworks tenzij nodig.
- Test met `python -m src.ai_visibility --dry-run` (geen API-calls) voor je echte calls doet.
