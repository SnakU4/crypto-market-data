# CMC100 Forward Lab – kostenloser Marktdaten-Collector v0.2

**Stand:** 5. November 2026. **Status: implementiert und mit künstlichen Testdaten geprüft, aber noch nicht live gegen die externen APIs getestet oder auf GitHub veröffentlicht.** Keine API-Schlüssel, keine OpenAI-API-Aufrufe, keine Orders, kein Echtgeldhandel.

## Aufgabe

Ein GitHub-Actions-Workflow ruft vor dem täglichen Crypto-Forecast zeitgestempelte **offizielle** CMC100-Konstituenten ab und ergänzt verfügbare kostenlose öffentliche Markt- und Derivatedaten:

- **Offizielle CMC100-Liste:** CMC ID, Symbol, Name, Gewicht, Index-Updatezeit; strikter Gatekeeper mit 100 eindeutigen IDs. KEIN stiller Ersatz durch Top-100-Marktkapitalisierungen.
- **CMC USD-Marktpreise:** Preis, 1h/24h/7d-Rendite, Volumen, Veränderung, Marktwert und Datenzeitstempel je CMC-ID.
- **Binance USD-M:** derzeit handelbare Perpetuals (nur sicherer baseAsset-Match), 1h-Kerzen (geschlossene Bars), Ret 1/6/24h/7d, Quote-Volumen, Volumenanomalie, Taker-Imbalance, 24h-Volatilität; Binance-geschätztes nächstes Funding; 24h-OI-Veränderung aus 1h-OI-History, soweit verfügbar.
- **Zusätzlicher Kontext:** CoinGecko-Globaldaten und DefiLlama-TVL nach Chains.
- **Offenes Research:** Web Search darf anschließend beliebige weitere Informationsarten untersuchen; die Pipeline ist die *Grundversorgung*, KEIN abschließendes Quellenverzeichnis.

**Wichtig:** Funding im Snapshot ist eine *geschätzte kommende Funding-Rate*, keine bestätigte Zahlung. Binance-OI-Daten stammen aus dem bei der Abfrage verfügbaren Historien-Endpunkt; vergangene Punkt-in-Zeit-Stände außerhalb der Retention können später fehlen. USD-M-Kontrakte mit Mengenpräfixen (z.B. `1000PEPEUSDT`) werden bewusst NICHT automatisch als identische Spot-Token klassifiziert. Datenfehler werden nicht mit Nullen gefüllt.

## Inbetriebnahme auf GitHub (einmalig)

1. Lege ein neues **öffentliches** GitHub-Repository an, z.B. `crypto-v6-market-data`. Entpacke dieses ZIP und lade den **gesamten Inhalt des Ordners** hoch, inklusive `.github/workflows/snapshot.yml` (nicht den übergeordneten Ordner zusätzlich).
2. Öffne im Repository **Actions → CMC100 Market Snapshot → Run workflow**. Der Workflow benötigt keine Secrets und verwendet Python 3.12 sowie die Standardbibliothek.
3. Prüfe im Actions-Protokoll, ob `Fetch official universe and public market features` erfolgreich war. Bei fehlendem CMC100-API-Zugriff **muss** der Lauf scheitern und `docs/status.json` enthält die Fehlermeldung. Ein PARTIAL der Börsendaten bei vollständiger offizieller CMC100-Liste darf publiziert werden, mit sichtbaren Coverage-Kennzahlen.
4. Unter **Settings → Pages → Build and deployment** wähle **GitHub Actions** als Quelle. Stelle sicher, dass GitHub Actions die durch den Workflow angeforderten Berechtigungen (`contents: write`, `pages: write`, `id-token: write`) verwenden darf. Danach bei Bedarf den Workflow erneut manuell starten.
5. Sobald Pages erfolgreich veröffentlicht ist, lautet die Adresse im Regelfall `https://DEIN-USERNAME.github.io/crypto-v6-market-data/`; prüfe sie konkret. Die KI soll `forecast_context.md` lesen sowie `latest.json` und `status.json` für Zeitstempel, Abdeckung und Datenlücken prüfen. **Das ist eine Platzhalter-Adresse – ohne echten GitHub-Benutzernamen keine gültige URL.**
6. Führe einen einmaligen Test *in ChatGPT mit Websuche* durch: Öffnet ChatGPT diese Seiten wirklich? Kann es die 100 CMC-IDs sowie Preis-, OI- und Funding-Felder reproduzieren? Wenn nein, liegt eine Webzugriffs- oder Crawling-Grenze vor; keine Vollständigkeit behaupten.
7. Erst **danach** die bestehende geplante Aufgabe `Krypto V6 Prediction Tournament` um die **tatsächlich erreichbare konkrete Pages-URL** ergänzen. Bis dahin bleibt die Aufgabe unverändert; ein nicht veröffentlichtes Repository kann sie nicht beliefern.

## Zeitplan und Data-Lag

GitHub Actions ist derzeit für 23:37 und 23:47 **UTC** täglich konfiguriert. Dies sind *geplante* Ausführungen, keine garantierten Startzeiten. Jede Datei enthält echte Capture-Zeiten und Quellzeitpunkte. GitHub Actions kann verzögert starten; Pages kann verzögert aktualisiert werden. Die bestehende ChatGPT-Prognose um 00:00 UTC darf nur einen Snapshot benutzen, der beim tatsächlichen Forecast-Freeze bereits publiziert war und keine zukünftigen Werte enthält.

Bei einem fehlgeschlagenen Collector-Lauf darf ChatGPT nicht automatisch den letzten JSON-Stand als frisch behandeln. Prüfe `status.json` und `snapshot_completed_utc`; wenn die Daten zu alt sind, kennzeichne `DATA_STALE` oder `DATA_UNAVAILABLE`. Der ChatGPT-Lauf kann sich selbst verzögern; er muss den tatsächlichen Freeze separat dokumentieren. Ein GitHub-Commit nach dem ursprünglichen 00:00-UTC-Soll-Cutoff darf NICHT rückwirkend als 00:00-Datenstand gelten.

## Ausgabedateien

- `docs/latest.json`: vollständige Original-CMC100-Liste, quantitative Features und Quellen-URLs, inklusive fehlender Daten.
- `docs/latest.csv`: eine flache Zeile pro offiziellem Coin, geeignet für Jupyter.
- `docs/forecast_context.md`: kompaktes öffentlich lesbares 100-Coin-Panel für ChatGPT.
- `docs/index.html`: öffentliche Übersicht mit eingebettetem 100er-Panel.
- `docs/status.json`: Coverage und Fehlermeldungen.
- `docs/archive/YYYYMMDD/UTC_TIMESTAMP_HASH.json`: archivierte, nicht überschreibbare PIT-Reports, die eine separate spätere Jupyter-Auswertung ermöglichen.

**Keine Einträge, keine Scores und keine Renditen werden vorgetäuscht.** Die im ZIP enthaltene `docs/index.html` ist bis zum ersten erfolgreichen GitHub-Lauf ausdrücklich nur ein Platzhalter.

## Qualitäts-Gates

Die Pipeline meldet `DATA_PASS` nur bei 100 offiziell verifizierten CMC100-Mitgliedern, ≥95 vorhandenen und 90 Minuten frischen CMC-USD-Quotes sowie mindestens 60 exakt gematchten USD-M-Perpetuals sowie ≥90% geschlossenen Binance-Perp-Kerzen und ≥85% OI-Daten *unter diesen exakt gematchten Kontrakten*. Alle übrigen Fälle erhalten `DATA_PARTIAL` oder `FAILED_NO_OFFICIAL_UNIVERSE`. Für ein wissenschaftlich strenges `9/10` müssen wir zusätzlich historische Exchange-Daten unabhängiger Quellen und lückenlose Quellzeitstempel erreichen; `DATA_PASS` ist dafür noch **kein** empirischer Nachweis.

## Lokal testen

```bash
python -m unittest discover -s tests -v
python src/collector.py --max-workers 5
```

Der zweite Befehl erfordert öffentlichen Netzwerkzugang. In dieser ChatGPT-Laufzeit sind externe DNS-/HTTP-Aufrufe aus dem Python-Container nicht möglich. Die sechs Unit-Tests prüfen die CMC100-Validierung, ID-Mapping, Kontraktzuordnung, Ausschluss nicht geschlossener Kerzen, OI-Lookahead und die CSV-/JSON-Ausgabe. **Echte externe API-Response-Tests fehlen bis zur ersten GitHub-Ausführung.**

### Quellen / API-Dokumentation

- CMC100 offiziell: https://coinmarketcap.com/api/documentation/pro-api-reference/cmc-index/
- CMC Keyless API: https://coinmarketcap.com/api/documentation/pro-api-reference/keyless-public-api/
- CMC Quotes Latest: https://coinmarketcap.com/api/documentation/pro-api-reference/cryptocurrency/
- Binance USDⓈ-M: https://developers.binance.info/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data
- DefiLlama API: https://github.com/DefiLlama/api-docs/blob/main/llms-free.txt
- GitHub Actions Zeitplanung: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule
- Pages Deployment: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
