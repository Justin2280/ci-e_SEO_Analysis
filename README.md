# CI Search Manager

Eigen alternatief voor de IONOS "AI Search Manager", gebouwd voor ci-engineers.com.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # vul keys in
python -m src.ai_visibility --dry-run
python -m src.ai_visibility
```

## Benodigde keys / toegang
| Wat | Waar | Nodig voor |
|---|---|---|
| OPENAI_API_KEY | platform.openai.com → API keys | ChatGPT-vermeldingen |
| ANTHROPIC_API_KEY | console.anthropic.com | Claude-vermeldingen |
| GEMINI_API_KEY | aistudio.google.com → Get API key | Gemini-vermeldingen |
| WP_APP_PASSWORD | WordPress → Gebruikers → Profiel → Application Passwords | Pagina's lezen/schrijven via REST API |
| Google Search Console | Google Cloud project → Search Console API aanzetten → service account → in GSC als gebruiker toevoegen | Echte ranking-/klikdata (module 3) |

Modelnamen staan in `.env` — controleer of ze nog actueel zijn bij de providers.

## Kosten
De AI-zichtbaarheidscheck doet (aantal vragen × 3 providers) calls per run. Met ~15 vragen wekelijks blijft dat op enkele euro's per maand.

## Structuur
```
CLAUDE.md            instructies voor Claude Code
config/queries.yaml  de vragen die aan de AI's gesteld worden + merknamen/concurrenten
src/ai_visibility.py AI-zichtbaarheidscheck (v1)
src/wp_client.py     WordPress REST API-helper
data/results/        JSONL-output per run
```
