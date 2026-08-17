# Evaluatiematrix-assistent

Webapplicatie voor het opstellen en beoordelen van tender-evaluatiematrixen (EMVI/BPKV).
Draait lokaal op je eigen computer, of gehost (bijv. op Render) als aparte subwebsite.
Alleen de tekst die je expliciet laat analyseren wordt naar de gekozen AI-provider
gestuurd (OpenAI, OpenRouter, of NVIDIA NIM) — zie **Instellingen** in de app.

## Lokaal opstarten

Eenmalig — zorg dat Python 3.11+ geïnstalleerd is. Dubbelklik daarna op `start.ps1`
(of run in PowerShell):

```powershell
.\start.ps1
```

Dit maakt de eerste keer automatisch een virtuele omgeving aan, installeert de
dependencies, en opent de app in je browser op `http://127.0.0.1:5151`.

## AI-provider instellen

Ga in de app naar **Instellingen**, kies een provider (OpenAI, OpenRouter, of NVIDIA NIM)
en vul de bijbehorende API-key in. Deze wordt lokaal opgeslagen in `.env` (nooit gedeeld,
nooit gecommit — zie `.gitignore`). Zonder key werkt alles behalve de AI-functies
(documenten uploaden, matrix handmatig samenstellen en exporteren naar Excel werken
sowieso).

## Status

Alle 8 fasen uit de oorspronkelijke spec (`evaluatiematrix-app-spec.md`) zijn gebouwd:
projectbeheer, documentupload + tekstextractie, AI-matrixgeneratie (tweetraps
extractie+synthese voor grondigheid), matrix reviewen/vaststellen, leveranciers/offertes
toevoegen, AI-scoring, handmatige score-controle, vergelijkingsdashboard, en volledige
Excel-export met scores en formules.

## Hosten als publieke (sub)website (bijv. op Render)

De app is een gewone Flask-applicatie en kan op elk Python-hostingplatform draaien.
Voor Render.com (gratis/goedkope tier, koppelt automatisch aan deze GitHub-repository):

1. Maak een gratis account op [render.com](https://render.com) en koppel je GitHub-account.
2. **New +** → **Web Service** → kies deze repository (`Evaluatiematrix`). Render herkent
   `render.yaml` automatisch (Python, `pip install -r requirements.txt`,
   `gunicorn app.wsgi:app`).
3. Zet bij **Environment** de volgende variabelen (nooit in code/git, alleen hier):
   - `APP_USERNAME` / `APP_PASSWORD` — inlogbeveiliging voor de hele site (zonder deze
     twee staat de app volledig open, dus stel ze altijd in bij een publieke deploy).
   - `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` — optioneel, kan ook later via het
     **Instellingen**-scherm in de app zelf (dan schrijft de app naar een lokaal
     `.env`-bestand op de server-schijf, dat *op de gratis Render-tier bij elke
     herstart/redeploy verdwijnt* — voor blijvende instellingen zijn env vars hier
     robuuster).
4. Deploy. Render geeft een `https://<naam>.onrender.com`-adres.
5. Voor een eigen subdomein (bijv. `matrix.testedwin.nl`): voeg dat toe bij Render onder
   **Settings → Custom Domains** — Render toont dan een CNAME-doel. Zet dat CNAME-record
   bij je domeinbeheer (Strato) voor het subdomein; testedwin.nl zelf (op Netlify) hoeft
   niet aangeraakt te worden.

**Let op — gratis Render-tier:**
- De schijf is niet-persistent: geüploade documenten en de database (`projects/`)
  verdwijnen bij elke herstart/redeploy/inactiviteit. Geschikt om te demonstreren/testen,
  niet om er echt tenderdata langdurig in te bewaren. Voor permanente opslag is een
  betaald abonnement met een *persistent disk* nodig.
- De gratis service "slaapt" na een periode van inactiviteit; de eerste request daarna is
  traag (koude start).
- AI-aanroepen (vooral met een gratis/gedeeld AI-model) kunnen enkele minuten duren; de
  gunicorn-workertimeout staat daarom op 600 seconden (`render.yaml`).

## Projectdata (lokaal)

Alles staat lokaal onder `projects/`: één SQLite-database
(`projects/evaluatiematrix.db`) met alle matrixdata, en per project een map met
de geüploade brondocumenten (`projects/<project_id>/input/`). Deze map staat in
`.gitignore` en hoort nooit in de git-geschiedenis.
