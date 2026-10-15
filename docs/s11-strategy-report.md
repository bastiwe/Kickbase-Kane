# Automatischer S11-Strategiereport

Eigenständiger S11-Report mit eigener GitHub-Aktion und eigener Mail. Die
bestehenden Fast-1T- und Abendberichte enthalten keine S11-Strategieauswertung.
Es sind keine neuen Zugangsdaten erforderlich.

## Ausführen und empfangen

In GitHub unter **Actions → Run S11 Strategy Report → Run workflow** starten.
Alternativ lokal `python s11_strategy_report.py` ausführen. Mit `--no-email`
entstehen nur Dateien. Die Aktion
nutzt weiterhin `KICK_USER`, `KICK_PASS`, `EMAIL_USER`, `EMAIL_PASS` aus den
vorhandenen Secrets bzw. der lokalen `.env`. Mit `KICK_LEAGUE_NAME` kann lokal die
Liga gewählt werden; die neue GitHub-Aktion liest dafür auch die Repository-Variable
`KICK_LEAGUE_NAME`. Vorgabe bleibt „Die Spätzünder“. `REPORT_LEAGUE_ID` und
`REPORT_USER_ID` funktionieren weiterhin für den lokalen Report-Aufruf.

Die neue Auswertung wird ausschließlich über die separate Aktion manuell
gestartet. Sie verschickt eine eigene Mail mit Betreff
„Kickbase S11-Strategie – eigenständiger Report“, HTML-Inhalt und HTML-Anhang.
Fast-Report und Abendreport behalten ihren bisherigen Versand und Zeitplan.

Der separate Workflow stellt `s11_strategy_report.html` und
`s11_strategy_report.json` als Artifact **s11-strategy-report** für sieben Tage
bereit. Sie enthalten private Liga-/Kaderdaten. Der bestehende Mail-Empfänger
bleibt unverändert (`EMAIL_USER`). Fehlt `EMAIL_USER` oder `EMAIL_PASS`, überspringt
der S11-Report den Versand; die Dateien entstehen trotzdem. Ein SMTP-Fehler lässt
den Lauf scheitern, fertige Dateien werden trotzdem als Artifact bereitgestellt.

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

Unrealisierte MW-Steigerungen werden nie auf Cash addiert. **Eigene Spieler mit
aktuellem MW über 25.000.000 € sind strikt vor Verkauf geschützt** („Big Boys“).
Maßgeblich ist der aktuelle Live-MW, nicht der prognostizierte MW. Genau
25.000.000 € ist noch nicht geschützt. Der Schutz gilt in allen drei Szenarien,
Vergleichsaufstellungen und Markt-/Tauschalternativen, auch bei Verletzung,
schwachen Punkten oder negativem Budget. Der Optimierer erzwingt keinen Einsatz:
geschützte Spieler können auf der Bank bleiben. Ihr MW wird nicht als möglicher
Verkaufserlös eingeplant. Sie zählen auch auf der Bank zum Vereinslimit und zum
16er-Kaderlimit.

Alle übrigen, nicht aufgestellten eigenen Spieler werden in jedem Plan verkauft.
Der Restkader besteht aus elf Startern plus eventuell geschützten Reserven.
Ist das Budget damit nicht auszugleichen, wird „nicht finanzierbar“ gemeldet,
statt einen geschützten Spieler zum Verkauf vorzuschlagen. Teure Marktspieler
sind weiterhin mögliche Käufe; der Schutz betrifft ausschließlich eigene Spieler.
Verkäufe zum prognostizierten MW
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
Startelfoptimierer. Der eigenständige Report nutzt die mit dem Fast-Report
geteilte Funktion `generate_fast_report_data()` ausschließlich zum Laden der Daten
und zur frischen 1T-Modellberechnung. Diese Funktion verschickt keine Mail und
wendet keinen Tradingfilter an. Der S11-Report ergänzt vorhandene LI-Signale und
übergibt den gerade erzeugten Prognosesnapshot. Der vollständige Markt
wird ohne den MW-Tradingfilter ausgewertet; auch Spieler mit
negativer MW-Prognose können sportliche Verstärkungen sein.

Punktebasis ist der vorhandene Schnitt der letzten drei Spiele, ersatzweise
Saisonschnitt, ersatzweise Vorsaisonschnitt. Falls im Planner-Payload eine
LI-Quote vorliegt, wird damit gewichtet. Ohne Quote wird die Einsatzunsicherheit
kenntlich gemacht. Historische Schnitte sind Vergleichswerte und keine neue
trainierte Spieltagsprognose. Ausfallstatus, fehlende Punkte, fehlende Position,
fehlender Verein oder ungültige Preise schließen einen Spieler aus der Elf aus.
Verkaufen lässt sich ein eigener Spieler nur, wenn er nicht geschützt ist.

Fehlende MW-Prognosen werden sichtbar als unsichere Annahme „unverändert“
behandelt. Fehlendes Cash oder ein fehlender eigener MW verhindern eine belastbare
Optimierung. Timeout und Unlösbarkeit werden explizit gemeldet; nur vollständig
gelöste Optimierungen heißen `optimal`. Die Reports nennen Rechenannahmen,
Abrufzeit und Status pro Spieler. Eine sportliche Empfehlung bleibt von der
Qualität und Aktualität der vorhandenen Punkte-/Statusdaten abhängig.

## Tests

`python -m unittest discover -s tests -p "test_*strategy*.py" -v`

Die Tests vergleichen den Solver mit vollständiger Enumeration kleiner Kader und
prüfen Formationen, Budget, MW-Effekt, Vereinslimit, Angebote, negative/fehlende
Punkte, LI-Gewichtung, Status, unbekannte Daten, Solver-Timeout, HTML-Escaping,
Dateiausgabe und den vorhandenen SMTP-Transport mit einem Mock. Zusätzliche
Tests prüfen die strikte 25-Mio.-Grenze, geschützte verletzte Bankspieler,
Finanzierbarkeit ohne deren Verkauf, Vereins-/Kaderlimit, eigenständigen Versand
und die Trennung von bestehenden Reports.
