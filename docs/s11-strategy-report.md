# Automatischer S11-Strategiereport

Die vorhandenen Fast-1T- und Abendberichte enthalten zusätzlich eine automatisch
berechnete S11-Auswertung. Es sind keine neuen Zugangsdaten erforderlich.

## Ausführen und empfangen

In GitHub unter **Actions → Run Fast 1T Predictions and S11 Strategy → Run workflow**
starten. Alternativ lokal `python daily_predictions_fast.py` ausführen. Die Aktion
nutzt weiterhin `KICK_USER`, `KICK_PASS`, `EMAIL_USER`, `EMAIL_PASS` aus den
vorhandenen Secrets bzw. der lokalen `.env`. Mit `KICK_LEAGUE_NAME` kann lokal die
Liga gewählt werden; Vorgabe bleibt „Die Spätzünder“. `REPORT_LEAGUE_ID` und
`REPORT_USER_ID` funktionieren weiterhin für den lokalen Report-Aufruf.

Die neue Auswertung steht direkt in der vorhandenen Report-Mail. Der Abendreport
verschickt zusätzlich die HTML-Datei als Anhang und erzeugt weiterhin den
interaktiven Startelfoptimierer. Die bestehenden automatischen Abendläufe
übernehmen die Auswertung nach Übernahme der Änderung. Der Fast-Workflow bleibt
manuell auslösbar.

Beide Workflows stellen `s11_strategy_report.html` und
`s11_strategy_report.json` als Artifact **s11-strategy-report** für sieben Tage
bereit. Sie enthalten private Liga-/Kaderdaten. Der bestehende Mail-Empfänger
bleibt unverändert. Ohne `EMAIL_USER` überspringt der Fast-Report wie bisher den
Versand; die Dateien entstehen trotzdem. Ein SMTP-Fehler lässt den Lauf scheitern.

## Was berechnet wird

- **Maximale Punkte:** höchste Summe bewerteter Punkte bei Cash ≥ 0.
- **Ausgewogen:** höchste Summe bei mindestens 1.000.000 € Restbudget. Eine
  nicht finanzierbare Variante wird ausdrücklich als nicht machbar ausgegeben.
- **Maximaler Budgetpuffer:** größtes Restbudget mit vollständiger zulässiger Elf;
  hier gibt es keine Mindestpunktzahl.

Ein ganzzahliger Optimierer (`scipy.optimize.milp`) prüft alle Formationen aus
`features.ai_advisor.FORMATIONS`, genau elf Spieler, höchstens drei je Verein und
das Budgetlimit. Es gibt keine Beschränkung auf die teuersten oder punktbesten
Kandidaten. Vereinslimit und Puffer können über die Python-Funktion
`build_strategy_report(payload, buffer=..., club_limit=...)` angepasst werden.
Das Vereinslimit ist eine Planungsannahme dieser Community.

Jeder Marktspieler wird zusätzlich durch eine eigene Optimierung mit erzwungener
Aufstellung geprüft. So entstehen auch Kombinationen mit mehreren Verkäufen und
Käufen. Als S11-relevant gelten punktstärkere Varianten gegenüber der besten
finanzierbaren eigenen Elf und Varianten, die erstmals eine finanzierbare Elf
ermöglichen. Angezeigt werden Käufe, Verkäufe, Punkte und Budget. Differenzen
beziehen sich ausdrücklich auf die stärkste eigene Elf ohne Budgetzwang.
Einzelne Ergebnisse sind alternative Pläne und nicht miteinander addierbar.

## Budget und Zeitpunkt

Ziel ist **morgen 06:00 Europe/Berlin**. Nur ein davor liegendes nächstes
22-Uhr-Update wird berücksichtigt. Nach 22 Uhr bleibt der aktuelle MW für die
Rechnung bis morgen früh unverändert. Die separat ausgewiesene aktuelle
1T-Prognose bezieht sich trotzdem auf die nächste MW-Änderung.

`Cash morgen = Cash jetzt + prognostizierte Verkaufserlöse − geplante Kaufpreise`

Unrealisierte MW-Steigerungen werden nie auf Cash addiert. In jedem Plan werden
**alle nicht aufgestellten eigenen Spieler verkauft**; der Restkader besteht aus
genau elf Spielern. Das maximiert die verfügbaren Mittel für die Startelf und
verzichtet ausdrücklich auf eine Bank/Trader. Verkäufe zum prognostizierten MW
sind Annahmen, keine garantierten Angebote. Login- und Transferboni werden ohne
bestätigte Auszahlung nicht eingerechnet.

Käufe werden mit eigenem Gebot, sonst Angebotspreis, sonst aktuellem MW kalkuliert.
Nur Angebote mit bekanntem Ablauf zwischen Abruf und morgen 06:00 kommen in die
Optimierung. Spätere, abgelaufene oder undatierte Angebote werden mit Grund
aufgeführt. Ein Preis garantiert keinen Zuschlag; spätere Verfügbarkeit des
Verkaufserlöses garantiert keine sofortige Kaufkraft. Andere offene Gebote müssen
vor Umsetzung zurückgezogen werden. Die Funktion führt keine Transfers aus.

## Datenbasis und Grenzen

Die Auswertung verwendet `build_lineup_payload`, also dieselben Kickbase-Clients,
Live-Marktwerte, Budgetabfrage und Historienfunktionen wie der bestehende
Startelfoptimierer. Beide Report-Pipelines trainieren ihre bisherigen Modelle
und geben den gerade erzeugten Prognosesnapshot weiter. Der vollständige Markt
wird **vor** dem bisherigen MW-Tradingfilter ausgewertet; auch Spieler mit
negativer MW-Prognose können sportliche Verstärkungen sein.

Punktebasis ist der vorhandene Schnitt der letzten drei Spiele, ersatzweise
Saisonschnitt, ersatzweise Vorsaisonschnitt. Falls im Planner-Payload eine
LI-Quote vorliegt, wird damit gewichtet. Ohne Quote wird die Einsatzunsicherheit
kenntlich gemacht. Historische Schnitte sind Vergleichswerte und keine neue
trainierte Spieltagsprognose. Ausfallstatus, fehlende Punkte, fehlende Position,
fehlender Verein oder ungültige Preise schließen einen Spieler aus der Elf aus.
Verkaufen lässt er sich weiterhin.

Fehlende MW-Prognosen werden sichtbar als unsichere Annahme „unverändert“
behandelt. Fehlendes Cash oder ein fehlender eigener MW verhindern eine belastbare
Optimierung. Timeout und Unlösbarkeit werden explizit gemeldet; nur vollständig
gelöste Optimierungen heißen `optimal`. Die Reports nennen Rechenannahmen,
Abrufzeit und Status pro Spieler. Eine sportliche Empfehlung bleibt von der
Qualität und Aktualität der vorhandenen Punkte-/Statusdaten abhängig.

## Tests

`python -m unittest discover -s tests -p test_strategy_report.py -v`

Die Tests vergleichen den Solver mit vollständiger Enumeration kleiner Kader und
prüfen Formationen, Budget, MW-Effekt, Vereinslimit, Angebote, negative/fehlende
Punkte, LI-Gewichtung, Status, unbekannte Daten, Solver-Timeout, HTML-Escaping,
Dateiausgabe und den vorhandenen SMTP-Versand mit einem Mock.
