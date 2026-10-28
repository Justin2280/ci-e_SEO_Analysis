# Actieplan SEO ci-engineers.com — Nederlandse site

Opgesteld: 2026-09-23. Bronnen: volledige site-audit van 23-09 (57 Nederlandse pagina's), Search Console
(22-08 t/m 18-09) en AI-zichtbaarheidsmeting van 21-09. De Engelse site (`/en/`) valt buiten dit plan.

Volgorde = prioriteit. Elke taak heeft een afvinkvakje, een geschatte tijd en waar je het doet.

---

## Samenvatting

| # | Wat | Waarom | Tijd |
|---|---|---|---|
| 1 | Redirects voor oude URL's | 22 oude pagina's die Google nog toont geven een 404 — samen ±2.200 vertoningen/maand weg | 1 uur |
| 2 | "Hello world!" verwijderen | Standaard testbericht staat live en is indexeerbaar | 2 min |
| 3 | Archiefpagina's op noindex | 5 dunne pagina's zonder description in Google | 10 min |
| 4 | H1-koppen op 11 pagina's | Hoofdpagina's (werken-bij, contact, over CI) hebben geen H1 | 30 min |
| 5 | Alt-teksten | 327 afbeeldingen zonder alt; 2 logo's staan op elke pagina | 1–2 uur |
| 6 | Homepage-title | Staat op positie 58 voor "ingenieursbureau"; het woord staat niet in de title | 5 min |
| 7 | JobPosting-schema op vacatures | Vacatures kunnen dan in Google for Jobs verschijnen | 1 uur |
| 8 | Twee trage pagina's | Net boven 2 s laadtijd; rest van de site is snel | 30 min |
| 9 | Pagina "Diensten / Detachering" | Er is geen pagina voor opdrachtgevers die een ingenieursbureau of detachering zoeken | 1 dag |
| 10 | Projectpagina's aanvullen | 19 projectpagina's hebben minder dan 300 woorden | doorlopend |
| 11 | Nieuws + AI-zichtbaarheid | 1 nieuwsbericht (dec 2024); 0 van 30 AI-antwoorden noemt CI-Engineers | doorlopend |

---

## Fase 1 — Deze week (snelle winst, samen ±2 uur)

### 1. Redirects (301) voor oude URL's — hoogste prioriteit

Na de nieuwe site-opbouw verwijzen de oude `/project/…`-adressen netjes door, maar de onderstaande
adressen geven een **404**. Google toont ze nog steeds: `/over-ons/` (785 vertoningen), `/vacatures/` (722)
en `/ons-team/` (240, positie 7,5 en 9 klikken) zijn verloren bezoekers.

**Hoe:** plugin *Redirection* (gratis) of Yoast Premium → Redirects. Type **301**.

| Vertoningen | Oude URL | Nieuwe URL |
|---:|---|---|
| 785 | `/over-ons/` | `/over-ci/` |
| 722 | `/vacatures/` | `/werken-bij-ci/` |
| 240 | `/ons-team/` | `/over-ci/` |
| 147 | `/vacatures/ontwerpleider-civiele-techniek/` | `/werken-bij-ci/ontwerpleider/` |
| 74 | `/diensten/` | `/` (later: nieuwe dienstenpagina, zie taak 9) |
| 70 | `/project/oosterweelverbinding/` | `/projecten/de-oosterweelverbinding/` |
| 26 | `/tweede-coentunnel/` | `/projecten/tweede-coentunnel/` |
| 24 | `/project/krammersluizen/` | `/projecten/renovatie-krammersluizen/` |
| 22 | `/sectoren/` | `/` (later: dienstenpagina) |
| 12 | `/de-groene-boog/` | `/projecten/de-groene-boog/` |
| 12 | `/sponsoring/` | `/over-ci/` |
| 11 | `/reconstructie-knooppunt-de-nieuwe-meer/` | `/projecten/reconstructie-knooppunt-de-nieuwe-meer/` |
| 10 | `/project/blankenbrugverbinding/` | `/projecten/blankenburgverbinding/` |
| 7 | `/keersluis-kornwerderzand/` | `/projecten/keersluis-kornwerderzand/` |
| 7 | `/vacatures/modelleur-civiele-techniek/` | `/werken-bij-ci/` |
| 7 | `/vacatures/solliciteren/` | `/werken-bij-ci/` |
| 6 | `/certificaten/` | `/over-ci/` |
| 4 | `/project/` | `/projecten/` |
| 3 | `/blankenburgverbinding/` | `/projecten/blankenburgverbinding/` |
| 2 | `/project/rijnlandroute-n206-ir-g-tjalma-weg/` | `/projecten/rijnlandroute/` |
| 1 | `/ci-engineers-is-lid-geworden-van-nlingenieurs/` | `/nieuws/ci-engineers-is-lid-geworden-van-nlingenieurs/` |
| 1 | `/privacy/` | `/privacy-policy/` |

- [ ] Alle 22 redirects aangemaakt
- [ ] Extra vangnet: regex-redirect `^/vacatures/.*` → `/werken-bij-ci/`
- [ ] Controle: elk oud adres in de browser openen → komt op de nieuwe pagina uit
- [ ] Search Console → Indexering → Pagina's → "Niet gevonden (404)": over 2–4 weken nalopen op nieuwe 404's

### 2. Testbericht "Hello world!" verwijderen

- [x] WordPress → Berichten → "Hello world!" → Prullenbak (en prullenbak legen)
- [ ] Categorie "Uncategorized" hernoemen naar "Nieuws" of leeg laten (dan verdwijnt het archief vanzelf)

### 3. Archiefpagina's uit Google houden

Deze pagina's zijn automatisch door WordPress gemaakt: weinig tekst, geen description, en ze concurreren met
de echte pagina's `/projecten/` en `/nieuws/`.

- `/category/nieuws/`, `/category/projecten/`
- `/tag/afgerond/`, `/tag/lopend/`
- `/author/ci-engineers/`

**Hoe (Yoast):** SEO → Instellingen →
- [x] Taxonomieën → Categorieën: "Toon categorieën in zoekresultaten" **uit**
- [x] Taxonomieën → Tags: **uit**
- [x] Geavanceerd → Auteursarchieven: **uitschakelen** (één auteur, geen meerwaarde)
- [x] Controle: `/sitemap_index.xml` bevat daarna geen category-/tag-/author-sitemaps meer

### 4. H1-koppen instellen (11 pagina's)

In Elementor staat de paginatitel als **H2**. Oplossing per pagina: klik de bovenste kop aan →
tabblad Inhoud → *HTML-tag* → **H1**. De tekst hoeft niet te veranderen; kleine verbeteringen staan erbij.

| Pagina | Huidige kop (H2) | Voorstel H1 |
|---|---|---|
| `/over-ci/` | OVER CI-ENGINEERS | Over CI-Engineers: civiel ingenieursbureau |
| `/werken-bij-ci/` | WERKEN BIJ CI-ENGINEERS | Werken bij CI-Engineers |
| `/werken-bij-ci/constructeur/` | CONSTRUCTEUR | Vacature Constructeur civiele techniek |
| `/werken-bij-ci/ontwerpleider/` | ONTWERPLEIDER | Vacature Ontwerpleider civiele techniek |
| `/werken-bij-ci/bim-modelleur/` | BIM-MODELLEUR | Vacature BIM-modelleur |
| `/werken-bij-ci/allplan-modelleur/` | Allplan-MODELLEUR | Vacature Allplan-modelleur |
| `/contact/` | Kom in contact met CI-ENGINEERS | Kom in contact met CI-Engineers |
| `/projecten/` | Projecten van CI | Projecten van CI-Engineers |
| `/nieuws/` | Nieuws van CI | Nieuws van CI-Engineers |
| `/nieuws/ci-engineers-is-lid-geworden-van-nlingenieurs/` | CI-engineers is lid geworden van NLingenieurs | (zelfde tekst, alleen H1 maken — in het bericht-template) |
| `/privacy-policy/` | Privacy Statement vanCI-Engineers b.v | Privacyverklaring CI-Engineers B.V. (spatie ontbreekt nu) |

- [x] 11 koppen omgezet naar H1
- [x] **Header-template:** de tekst "Menu" is nu een H2 op elke pagina → HTML-tag op `div` of `span` zetten
      (Elementor → Templates → Theme Builder → Header)
- [x] ~~Nieuwsbericht-template~~ — er is geen Single Post-template; nieuwsberichten zijn losse Elementor-pagina's. Bij elk nieuw bericht zelf de kop op H1 zetten.

---

## Fase 2 — Binnen 2 weken (techniek & vindbaarheid)

### 5. Alt-teksten bij afbeeldingen

327 van de 450 afbeeldingen hebben geen alt-tekst (belangrijk voor Google Afbeeldingen en toegankelijkheid).

**Eerst de template (lost 114 gevallen in één keer op):** deze 2 afbeeldingen staan op álle 57 pagina's:

- [x] `Logo-CI-Engineers-1.png` → alt: `CI-Engineers logo`
- [x] `koninklijke-nlingenieurs.png` → alt: `Lid van Koninklijke NLingenieurs`

**Daarna de Mediabibliotheek:** WordPress → Media → per afbeelding het veld *Alternatieve tekst* invullen.
Elementor neemt die tekst automatisch over. Beschrijf wat er te zien is + projectnaam, bijvoorbeeld
`Kademuur Amaliahaven tijdens de bouw`.

- [ ] Projectfoto's (±3 per projectpagina, 40 projectpagina's)
- [ ] Projectoverzicht `/projecten/` (42 afbeeldingen, grotendeels dezelfde projectfoto's → lost zich op via de Mediabibliotheek)
- [ ] Tip: bestanden als `Gemini_Generated_Image_j3c39w…png` bij een volgende upload een beschrijvende naam geven
      (bijv. `ci-engineers-kademuur-amsterdam.png`)

### 6. Homepage-title en belangrijkste titles

De homepage staat gemiddeld op positie 48; voor "ingenieursbureau" (220 vertoningen) op 58 en voor
"civiel ingenieursbureau" op 22. Het woord *ingenieursbureau* staat niet in de title.

- [x] Homepage (Yoast-blok onderaan de pagina → SEO-titel):
      `Civiel ingenieursbureau & detachering | CI-Engineers` (52 tekens)
- [x] `/over-ci/`: `Over CI-Engineers | Civiel ingenieursbureau in Nederland`
- [x] `/werken-bij-ci/`: `Werken bij CI-Engineers | Vacatures civiele techniek`
      (zoekterm "civiele techniek banen" en "ontwerper civiele techniek vacatures" hebben nu geen passende pagina)
- [x] Te lange title inkorten: `/projecten/ondergrondse-verbindingen-realisatie-toegangstunnels-kelder-thi/`
      (79 tekens) → `Toegangstunnels kelder THI | CI-Engineers`

### 7. Vacatures in Google for Jobs (JobPosting-schema)

De 4 vacaturepagina's hebben nu alleen algemeen *WebPage*-schema. Met *JobPosting*-schema kunnen ze in het
vacatureblok bovenaan Google verschijnen — gratis extra zichtbaarheid bij de tweede doelgroep (personeel).

- [x] Kiezen: plugin (bijv. *WP Job Openings*, of Yoast "Job Posting"-blok als dat in de licentie zit)
      of per vacature een JSON-LD-blok in een Elementor *HTML*-widget
- [x] Verplichte velden per vacature: titel, omschrijving, datum geplaatst, geldig tot, werkgever
      (CI-Engineers B.V. + logo), locatie, dienstverband; salarisindicatie sterk aanbevolen
- [x] Controleren met Google Rich Results Test (search.google.com/test/rich-results)
- [ ] Verlopen vacatures offline halen of `validThrough` bijwerken (anders waarschuwing in Search Console)

### 8. Trage pagina's (lage prioriteit)

Gemiddelde laadtijd is 1,4 s — prima. Alleen twee pagina's zaten net boven 2 s
(`/nieuws/ci-engineers-is-lid-geworden-van-nlingenieurs/`, `/projecten/amstel-hotel-kademuur-stabilisatie/`).

- [ ] Grote afbeeldingen op die pagina's comprimeren (WebP/AVIF, max. ±300 KB)
- [ ] Hostinger → LiteSpeed Cache: controleren dat pagina-cache en afbeeldingsoptimalisatie aan staan

---

## Fase 3 — Binnen een maand (content)

### 9. Nieuwe pagina: Diensten / Detachering

Opdrachtgevers zoeken op termen waar de site geen pagina voor heeft. De oude `/diensten/` en `/sectoren/`
bestaan niet meer.

| Zoekterm | Vertoningen/maand | Huidige positie |
|---|---:|---:|
| ingenieursbureau | 220 | 59 |
| engineering bureau | 95 | 24 |
| ingenieursbureau civiele techniek | 84 | 34 |
| civiel ingenieursbureau | 52 | 22 |
| ingenieursadviesbureau | 44 | 35 |
| ingenieursbureau infrastructuur | 30 | 62 |
| detachering civiele techniek | 28 | 64 |
| detacheringsbureau civiele techniek | 28 | 48 |

- [ ] Pagina **`/diensten/`** (of `/civiele-engineering/`): wat CI-Engineers doet — constructief ontwerp,
      berekeningen, BIM/Revit/Allplan-modellering, ontwerpleiding — met voorbeeldprojecten (links naar
      projectpagina's). Minimaal 600 woorden, H1 met "civiel ingenieursbureau".
- [ ] Pagina **`/detachering/`**: welke functies gedetacheerd worden, hoe het werkt, voor wie. H1 met
      "detachering civiele techniek".
- [ ] Beide in het hoofdmenu en vanaf de homepage linken
- [ ] Redirects `/diensten/` en `/sectoren/` (taak 1) daarna naar deze pagina's laten wijzen

### 10. Projectpagina's aanvullen (19 pagina's onder 300 woorden)

Projectpagina's scoren al goed op projectnamen (bijv. "blankenburg tunnel" positie 1,7, "rijnland route" 4,0).
Meer tekst = meer zoektermen waarop ze gevonden worden. Per pagina aanvullen met: opdrachtgever, rol van
CI-Engineers, technische uitdaging, oplossing, periode, gebruikte software.

Kortste eerst:

| Woorden | Pagina |
|---:|---|
| 191 | `/projecten/selectieve-onttrekking-ijmuiden/` |
| 204 | `/projecten/verlegging-schijnkoker-ringweg-r1/` |
| 217 | `/projecten/renovatie-krammersluizen/` |
| 223 | `/projecten/prinses-alexiaviaduct/` |
| 228 | `/projecten/blankenburgverbinding/` |
| 229 | `/projecten/de-groene-boog/` |
| 230 | `/projecten/tweede-coentunnel/` |
| 242 | `/projecten/fietsbrug-hoorn/` |
| 242 | `/projecten/vernieuwde-n31/` |
| 242 | `/projecten/bruggen-en-paviljoens-strandeiland/` |
| 247 | `/projecten/wegverbreding-a2-het-vonderen-kerensheide/` |
| 248 | `/projecten/onderdoorgang-vierpaardjes-venlo/` |
| 254 | `/projecten/westrandweg/` |
| 255 | `/projecten/saaone/` |
| 270 | `/projecten/canakkale-brug/` |
| 276 | `/projecten/amstelveenlijn/` |
| 279 | `/projecten/ovt-zuid/` |
| 286 | `/projecten/petrokemia/` |
| 292 | `/projecten/edespoort-ovt/` |

- [ ] Richtlijn: 2 projectpagina's per week → klaar in ±10 weken
- [ ] Kademuren-projecten (`herstel-kademuren-amsterdam`, `kademuurbouw-amaliahaven`,
      `amstel-hotel-kademuur-stabilisatie`) onderling linken: "kademuren" en "vervangen kademuren/kadeconstructies"
      hebben samen ±100 vertoningen/maand op positie 23–30
- [ ] Ook de pagina's `/contact/` (188 woorden) en `/nieuws/` (98 woorden) een korte inleidende alinea geven

### 11. Nieuws bijhouden

Er staat 1 nieuwsbericht op de site (december 2024). Een actieve nieuwspagina laat Google én AI-assistenten
zien dat het bedrijf actief is.

- [ ] Minimaal 1 bericht per maand: opgeleverd project, nieuwe collega, certificering, lidmaatschap, vakartikel
- [ ] Elk bericht linkt naar het bijbehorende project of de vacaturepagina

---

## Fase 4 — Doorlopend (AI-zichtbaarheid & autoriteit)

In de meting van 21-09 noemde **geen van de 30 antwoorden** (ChatGPT, Claude, Gemini) CI-Engineers. Wel genoemd:
Arcadis (19×), Sweco (18×), Witteveen+Bos (18×), Royal HaskoningDHV (17×), Antea Group (13×), Brunel (12×), YER (5×).
AI-assistenten baseren zich op wat er óver een bedrijf op andere sites staat.

- [ ] **Google Bedrijfsprofiel** aanmaken/controleren (naam, adres, telefoon, categorie "Ingenieursbureau", foto's)
- [ ] Bedrijfsgegevens overal identiek: website, LinkedIn, KvK, NLingenieurs-ledenlijst, Google Bedrijfsprofiel
- [x] Yoast → Instellingen → Site-representatie: organisatienaam, logo en profielen (LinkedIn) invullen
      (komt dan in het Organization-schema op elke pagina)
- [ ] Vermelding op NLingenieurs-ledenoverzicht met link naar ci-engineers.com controleren
- [ ] Opdrachtgevers/partners vragen om projectvermelding met link (bijv. bij een gezamenlijk project)
- [x] Optioneel: `llms.txt` in de root van de site (korte samenvatting voor AI-crawlers: wie, wat, diensten, contact)
- [ ] `config/queries.yaml` aanvullen met de echte zoektermen uit de tabel bij taak 9

---

## Status na controle op 2026-09-23 (avond)

Live gecontroleerd met een nieuwe scan (51 NL-pagina's, was 57 doordat de archieven uit de sitemap zijn):

| Signaal | Ochtend | Nu |
|---|---:|---:|
| Issues (NL) | 101 | 72 |
| Pagina's zonder H1 (NL) | 11 | **0** |
| Afbeeldingen zonder alt (NL) | 327 | 119 |
| Sitemaps | post, page, category, tag, author | post, page |
| JobPosting-schema op vacatures | 0 | 4 (geldig, `validThrough` 2027-03-31) |
| llms.txt | 404 | aanwezig (Yoast) |

Geverifieerd: "Hello world!" geeft 404; `/category/…` en `/tag/…` staan op `noindex, follow`; `/author/…` redirect naar home;
nieuwe titles staan live (home 52 tekens, over-ci 56, werken-bij 52, THI 41); "Menu" in de header is H6;
Yoast Organization-schema bevat LinkedIn.

**Bewust niet gedaan (besluit Justin):** taak 1 redirects, taak 8 LiteSpeed/compressie.
Let op bij taak 1: de 404's blijven vertoningen kosten zolang Google de oude URL's toont; `/ons-team/` stond op positie 7,5.

**Nog open, in volgorde:**
1. Alt-teksten projectfoto's (119 over, verspreid over de projectpagina's en `/projecten/`) — taak 5
2. Nieuwe pagina's Diensten en Detachering — taak 9
3. 19 dunne projectpagina's aanvullen — taak 10
4. Nieuws bijhouden — taak 11
5. Google Bedrijfsprofiel, NLingenieurs-vermelding, partnerlinks — fase 4
6. Klein: prullenbak legen, categorie "Uncategorized" hernoemen, salarisindicatie in JobPosting toevoegen,
   `validThrough` vóór 31-03-2027 verlengen, homepage-H1 "COMPLEXE<br>CIVIELE" (regelafbreking zonder spatie; Google leest "COMPLEXECIVIELE" → spatie vóór de `<br>` zetten)
7. `config/queries.yaml` aanvullen met echte zoektermen (repo)

---

## Wat de tooling in deze repo kan overnemen

- **Titles en descriptions** (taak 6, 10): `src/seo_suggest.py` maakt voorstellen; toepassen via
  `src/wp_client.py` pas na bevestiging (`JA`). Titles voorstellen staat nog op de ideeënlijst.
- **Controle na afloop**: de wekelijkse audit (maandag) laat zien of H1's, alt-teksten en noindex zijn opgelost.
  Voor een check buiten de weekrun: `python -m src.seo_audit`.
- **Redirects, H1's, schema en nieuwe pagina's** moeten in WordPress/Elementor zelf gebeuren.

## Meten of het werkt

| Signaal | Nu | Doel over 3 maanden |
|---|---|---|
| 404's met vertoningen in Search Console | 22 URL's | 0 |
| Pagina's zonder H1 (NL) | 11 → 0 (23-09) | 0 |
| Afbeeldingen zonder alt (NL) | 327 → 119 (23-09) | < 20 |
| Positie "civiel ingenieursbureau" | 22 | top 10 |
| Positie "ingenieursbureau civiele techniek" | 34 | top 20 |
| Vacatures met geldig JobPosting-schema | 0 → 4 (23-09) | 4 zichtbaar in Google for Jobs |
| AI-antwoorden die CI-Engineers noemen | 0 / 30 | ≥ 3 / 30 |
