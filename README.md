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

## Publiek bereikbaar maken — zelf hosten + gratis tunnel (huidige opzet)

In plaats van cloudhosting (die vrijwel altijd een creditcard vraagt, zelfs voor een
"gratis" tier) draait de app gewoon lokaal op je eigen computer, en maakt een gratis
tunnel-tool ([tunnelto.me](https://www.tunnelto.me/)) 'm bereikbaar op een eigen
subdomein — zonder creditcard, zonder cloudkosten, en zonder dataverlies (alles blijft
op je eigen schijf staan).

**Eenmalig instellen:**

1. `tunnelto` staat al geïnstalleerd (via Scoop). Maak een gratis account op
   [tunnelto.me](https://www.tunnelto.me/) en haal je token/dashboard-gegevens op.
2. Run `tunnelto` (zonder argumenten) in een PowerShell-venster om je account te
   koppelen — dit vraagt om het token uit je tunnelto-dashboard.
3. In je tunnelto-dashboard: voeg je eigen domein toe (bijv. `testedwin.nl`) en volg de
   getoonde instructies om bij je domeinbeheer (**Strato**) een TXT-record (eigendom
   bewijzen) en een wildcard A-record toe te voegen. Dit hoeft maar één keer.
4. Kopieer `secrets.local.ps1.example` naar `secrets.local.ps1` en vul een gebruikersnaam
   + wachtwoord in — dit bestand staat in `.gitignore` en komt dus nooit in de
   GitHub-repository terecht.

**Elke keer dat je de app publiek beschikbaar wilt maken:**

1. Start de app: `.\start-publiek.ps1` (laat dit venster open staan — dit is de
   inlogbeveiligde variant van `start.ps1`).
2. Open een **tweede** PowerShell-venster en run: `tunnelto add matrix.testedwin.nl 5151`
   (of jouw gekozen subdomein).
3. De site is nu bereikbaar op dat subdomein, met inlogscherm ervoor. Sluit beide
   vensters om 'm weer offline te halen.

**Let op:** je computer moet aanstaan (en niet in slaapstand) wil de site bereikbaar
zijn — dit is geen 24/7-cloudhosting, maar een gratis alternatief zonder de haken en ogen
daarvan (creditcard, dataverlies op gratis tiers, doorlopende kosten).

## Alternatief: wél cloudhosten (Render.com, kost ~$7/maand voor permanente opslag)

De repository bevat ook `app/wsgi.py` en `render.yaml` voor het geval je later alsnog
voor een 24/7-cloudoptie kiest. Render.com koppelt automatisch aan deze GitHub-repository
(gunicorn, `render.yaml`-configuratie staat al klaar) — zie de git-historie van dit
bestand voor de volledige stappen, of vraag het opnieuw uit.

## Projectdata (lokaal)

Alles staat lokaal onder `projects/`: één SQLite-database
(`projects/evaluatiematrix.db`) met alle matrixdata, en per project een map met
de geüploade brondocumenten (`projects/<project_id>/input/`). Deze map staat in
`.gitignore` en hoort nooit in de git-geschiedenis.
