# Changelog

## 0.2.49

- Markiert Formationen mit nichtnegativem Endbudget grün, mit negativem Endbudget gelb und nicht vollständig besetzbare Formationen rot.
- Hebt die aktive Formation zusätzlich mit einer Umrandung in ihrer jeweiligen Statusfarbe hervor.

## 0.2.48

- Ordnet die Managerbudget-Kacheln untereinander an und zeigt Cash, Kaderwert und Kaufkraft je Manager in getrennten Spalten.

## 0.2.47

- Behebt den Import des Manager-Audits, wenn GitHub Actions `latest.json` auf der Wurzelebene des Artefakts ablegt.

## 0.2.46

- Ein Klick auf einen freien Startelfplatz öffnet passende Kandidaten für genau diese Position.
- Für jeden Kandidaten wird das verbleibende Budget nach seiner Auswahl direkt angezeigt.

## 0.2.45

- Zeigt Namen, Cash, Kaderwert und Kaufkraft aller Manager als eigene Dashboard-Kachel.
- Synchronisiert den Manager-Audit des letzten Vollreports aus den geschützten GitHub-Actions-Artefakten.
- Kennzeichnet den eigenen API-Cashwert und die geschätzten Cashwerte der Mitmanager transparent.

## 0.2.44

- Der Startelfplaner ordnet die Spielerkacheln auf Desktop-Bildschirmen formationsgerecht auf einem Fußballfeld an; mobil bleibt die kompakte Liste erhalten.
- Bankspieler sind initial und nach dem Verschieben auf die Bank automatisch als Verkauf markiert. Beim Einsetzen in die Startelf wird die Markierung entfernt.

## 0.2.43

- Das Kaderwertdiagramm wird aus der vollständigen eigenen Transferhistorie rekonstruiert und am aktuellen, direkt von Kickbase gelieferten Kaderwert verankert.
- Historische Tage mit unvollständigen Marktwertdaten werden nicht mehr als zu niedrige Kaderwerte dargestellt.

## 0.2.42

- Transfermarkt und Handlungsbedarf lassen sich nun aufklappen und zeigen die letzten vier tatsächlichen täglichen Marktwertänderungen direkt aus der Kickbase-API.

## 0.2.41

- Die Prüfung nach „In Kickbase übernehmen“ versteht nun das aktuelle Kickbase-v4-Slotformat. Erfolgreich gespeicherte Aufstellungen werden nicht mehr fälschlich als Fehler gemeldet.

## 0.2.40

- Der mobile Startelfplaner lädt beim Öffnen die aktuelle Kickbase-Aufstellung und bietet nun „In Kickbase übernehmen“.
- Eine vollständige, positionsgerechte Elf aus dem echten Kader wird direkt über die Kickbase-API gespeichert.
- Simulierte Käufe werden vor der Übertragung erkannt und können nicht versehentlich in Kickbase gespeichert werden.

## 0.2.39

- „Beste 11“ bewertet innerhalb der zulässigen Budgetgrenze künftig Saison-Punkteschnitt, L3-Form, Startelfquote und ersten verfügbaren Gegner.
- Die 1T-Marktwertprognose wirkt nur als kleiner Tiebreaker und kann sportliche Punktedaten nicht überstimmen.
- Restbudget oberhalb der gewählten Grenze beeinflusst die Rangfolge nicht.

## 0.2.38

- Desktop-Ansicht des Startelfplaners erhält an Bankspielern sichtbare Schalter für „Verkauf“ und „Halten“.
- Die Restbudget-Kachel beobachtet die reale Kopfhöhe per ResizeObserver und bleibt beim Scrollen mit zusätzlichem Abstand vollständig unter dem Kopfbereich.

## 0.2.37

- „Beste 11“ ordnet die gefundene optimale Spielerkombination nun korrekt den Positionsplätzen der gewählten Formation zu.

## 0.2.36

- Die Kader-/Bankliste des mobilen Startelfplaners ist nach TW, ABW, MIT und ANG gruppiert.
- Dezente Positionsüberschriften und Trennlinien erleichtern das schnelle Scannen der Bank.

## 0.2.35

- Linkswisch markiert Spieler im mobilen Startelfplaner als unverkäuflich; ein weiterer Linkswisch entfernt die Halte-Markierung.
- Geschützte Spieler werden in „Beste 11“ und der Budgetrechnung nicht als Bankverkauf eingeplant.
- Geschützte Spieler erhalten eine grüne „HALTEN“-Kennzeichnung.

## 0.2.34

- Die Transfermarkt-Auswahl unter „Kauf simulieren“ ist nach Angebotsablauf sortiert; ablaufende Angebote stehen zuerst.

## 0.2.33

- Die feststehende Budget-Kachel im mobilen Startelfplaner berücksichtigt dynamisch die tatsächliche Höhe des Kopfbereichs.
- Restbudget und Budgetvorgabe bleiben dadurch beim Scrollen vollständig sichtbar.

## 0.2.32

- Im mobilen Startelfplaner lassen sich Transfermarktspieler mit frei eingetragenem Overpay als Kauf simulieren.
- Der Kaufpreis wird als Marktwert plus Overpay berechnet und fließt in Aufstellung, Bankverkäufe und Budgetgrenze ein.
- Simulierte Käufe können jederzeit einzeln entfernt werden.

## 0.2.31

- Der mobile Startelfplaner hat nun einen Schalter für die Budgetvorgabe: am Spieltag mindestens 0 EUR oder bis zu 5 Mio. EUR Defizit.
- „Beste 11“ optimiert seine Auswahl jeweils gegen die aktiv gewählte Budgetgrenze.

## 0.2.30

- „Beste 11“ berücksichtigt nun das Budget: Alle nicht aufgestellten Kaderspieler werden als Verkauf mit ihrem Marktwert gerechnet.
- Es werden nur punktstarke Kombinationen gewählt, die nach den geplanten Bankverkäufen mindestens -5 Mio. EUR Restbudget erreichen.
- Ist das selbst mit vollständigem Bankverkauf nicht möglich, zeigt der Planer einen klaren Hinweis statt eine irreführende Auswahl.

## 0.2.29

- Mobile Risikozeilen sind zweizeilig und überlagern Status und Betrag nicht mehr.
- Der Transfermarkt wird auf Smartphones als kompakte, mehrzeilige Kartenliste ohne horizontales Scrollen angezeigt.
- Rechtswisch funktioniert nun auch in der Startelf: Spieler werden auf die Bank verschoben und als Verkauf markiert.
- „Beste 11“ vergleicht alle gültigen Formationen und wählt die Kombination mit dem höchsten aktuellen Punkteschnitt.

## 0.2.28

- Mobiler Startelfplaner ergänzt: Startelf und Bank lassen sich per Drag-and-Drop oder Antippen planen.
- Rechtswisch auf einem Bankspieler markiert ihn als Verkauf; die Budget-Kachel zeigt Verkaufserlös, Restbudget und verbleibende Kadergröße.
- Die Kachel prüft sofort, ob nach Verkäufen noch eine gültige Kickbase-Formation möglich ist und nennt fehlende Positionen.

## 0.2.27

- Die Kaderwertgrafik beginnt nun am konfigurierten Ligastartdatum statt am frühesten verfügbaren Marktwert.
- `league_start_date` ist als Add-on-Einstellung verfügbar und wird auch von Voll- und Schnellreport verwendet.


## 0.2.26

- Die 1T-Kaderwert-Kachel zeigt die feste Kadergrenze `16` statt der Zahl verfügbarer Marktwertänderungen.
- Der Kaderzähler ist grün bei freiem Platz, gelb bei `16/16` und rot bei einer Überschreitung.


## 0.2.25

- Kaufkraft berücksichtigt nun auch eigene offene Gebote aus dem aktuellen Kickbase-Feld `uop` korrekt.
- Dadurch werden mehrere parallele Gebote, etwa auf Gruda, vollständig vom verfügbaren Maximalgebot abgezogen.


## 0.2.24

- Jede Kaderzeile zeigt nun direkt G/V seit dem eigenen Kauf, Kickbase-Gesamtpunkte und den aktuellen Kickbase-Punkteschnitt.
- Kaufpreise werden über die Liga-Transferhistorie geladen und pro Spieler zwischengespeichert; fehlende Kaufdaten werden nicht geschätzt.


## 0.2.23

- Das Dashboard kann „Vollreport“ und „Fast 1T“ direkt als GitHub-Action starten.
- Der dafür konfigurierte Fine-grained Token benötigt für `bastiwe/Kickbase-Kane` die Berechtigung `Actions: Read and write`; der fertige Snapshot wird danach weiterhin automatisch synchronisiert.


## 0.2.22

- Kacheln unter „Beste Chancen vor MW-Update“ sind nun aufklappbar und zeigen ebenfalls die vier letzten tatsächlichen Tagesänderungen eines Spielers.


## 0.2.21

- „Dein Kader · Wertentwicklung“ zeigt nun alle Kaderspieler statt nur fünf.
- Jede Zeile ist aufklappbar und lädt die vier letzten tatsächlichen täglichen Marktwertänderungen direkt aus der Kickbase-API.


## 0.2.20

- Kaderwertdiagramm nutzt nun die historische Marktwert-API von Kickbase statt einer vorausgesetzten lokalen SQLite-Historie.
- Der Verlauf berücksichtigt deinen verfügbaren Transferfeed; ohne zuordenbare ältere Transfers zeigt er transparent die historische Entwicklung des heutigen Kaders.


## 0.2.19

- Kaderwert-Kachel zeigt bei negativem Cash zusätzlich den bereinigten Gesamtwert: Kaderwert minus aktuellem Fehlbetrag.


## 0.2.18

- Live-Dashboard priorisiert Kickbase-Spielerprofile für Position, Status, Gesamtpunkte, Punkteschnitt, Minuten, Bilder, Vereins- und Marktwertdaten.
- Der GitHub-Snapshot bleibt auf die nicht von Kickbase gelieferten Werte beschränkt: Marktwertprognosen und LigaInsider-Signale.


## 0.2.17

- Dashboard zeigt unter dem verfügbaren Budget die Kaufkraft nach der Kickbase-33%-Regel, abzüglich eigener offener Gebote.
- Die erwartete Kaderentwicklung zeigt zusätzlich die tatsächlich erzielte Bilanz des letzten Marktwert-Updates aus der Kickbase-API.
- Die nicht handlungsrelevante Kennzahl „Trading-Chancen“ wurde entfernt.


## 0.2.16

- „Beste Chancen vor MW-Update“ zeigt ausschließlich Angebote mit Ablauf vor dem nächsten 22-Uhr-Update und mindestens +100.000 EUR erwarteter 1T-Steigerung.
- Die Kachel zeigt maximal sechs passende Spieler im 3×2-Raster.


## 0.2.15

- Lokale Schnellreport- und Vollreport-Buttons sowie die Fortschrittsanzeige aus dem Dashboard entfernt.
- Der Kopf zeigt stattdessen kompakt Quelle und Berliner Zeitpunkt des zuletzt geladenen Prognose-Snapshots.


## 0.2.14

- GitHub Actions veröffentlichen nach Voll- und Schnellreport einen kleinen Prognose-Artifact.
- Das Home-Assistant-Add-on kann diesen Snapshot mit einem Fine-grained GitHub-Token (Actions: Read-only) alle fünf Minuten abrufen.
- Sobald der GitHub-Sync konfiguriert ist, wird die lokale rechenintensive Vollreport-Planung im Add-on nicht gestartet.


## 0.2.13

- Dashboard startet ohne lokalen Report und lädt Kader, Cash, Transfermarkt, aktuelle Marktwerte, Positionen, Status, Punkte und Bilder direkt aus der Kickbase-API.
- Spielerprofile werden zehn Minuten lokal zwischengespeichert, damit wiederholtes Öffnen der Oberfläche die Kickbase-API nicht unnötig belastet.
- Prognosewerte bleiben bewusst vom letzten Hintergrundreport getrennt: Sie sind die einzige nicht von Kickbase gelieferte Kennzahl.


## 0.2.12

- Trading-Chancen beginnen nun erst ab einer erwarteten 1T-Marktwertsteigerung von +100.000 EUR.
- Namen, Vereine und Bilder werden für den Live-Kader und den Transfermarkt zusätzlich aus der lokalen Spielerhistorie ergänzt; numerisch gespeicherte Spieler-IDs werden dabei zuverlässig zugeordnet.
- Kaderwertdiagramm rekonstruiert den Verlauf aus dem eigenen Kickbase-Transferfeed und historischen Marktwerten, statt heutige Spieler rückwirkend anzunehmen.
- Vollreport im Home-Assistant-Add-on läuft mit begrenzter Parallelität und ohne das dort nicht benötigte 7T-Modell, damit der Raspberry Pi keinen Speicherabbruch bekommt.
- Fehler aus vom System beendeten Reportprozessen nennen nun den Rückgabecode bzw. das Signal im Dashboard.


## 0.2.11

- Schnellreport aktualisiert nun auch Namen, Vereine, Bilder und Marktmetadaten im Dashboard.
- Handlungsbedarf unterscheidet drohende Kaderverluste, Top-Chancen vor 22 Uhr und Nachtgebote bis 09 Uhr.
- Kaderwert-Entwicklungsdiagramm seit Saisonstart ergänzt.

## 0.2.10

- Report-Fortschritt direkt unter dem Dashboard-Kopf und den Report-Buttons platziert.

## 0.2.9

- Fortschrittsbalken für Vollreport und Schnellreport im Trading-Dashboard ergänzt.
- Zeigt Anmeldung, Datenabgleich, Modellberechnung, Markt- und Kaderauswertung sowie Abschluss an.

## 0.2.8

- Fast-Report repariert; er kann wieder Prognosen erzeugen und die E-Mail auslösen.
- Dashboard zeigt fehlende Prognosen nicht mehr als 0 EUR an.
- Vollreport aktualisiert Namen, Vereine, Bilder und Spielerdaten im Dashboard.
- Handlungsbedarf erklärt Marktwertverluste und nah ablaufende Angebote verständlich.

## 0.2.7

- Docker-Build in eine langlebige Python-Abhängigkeitsschicht und einen schnellen Anwendungscode-Checkout getrennt.
- Nach diesem einmaligen Update bleiben reine UI- und Dashboard-Updates deutlich schneller.

## 0.2.6

- Startelf-Optimierer in der Home-Assistant-Oberfläche durch ein fokussiertes Trading-Dashboard ersetzt.
- Zeigt Live-Budget, Kaderwert, erwartete 1T-Kaderentwicklung, Top-Chancen, Risikosignale und einen sortierbaren Transfermarkt.
- Vollreport und Schnellreport lassen sich direkt aus dem Dashboard starten.

## 0.2.5

- Top-Chance-Kacheln bewerten reine Trading-Chancen wieder unabhängig von der Startelfquote.
- Die Mindestschwelle von +50.000 EUR erwarteter 1T-Steigerung bleibt bestehen.

## 0.2.4

- Top-Chance- und Top-Pick-Kacheln verlangen nun mindestens +50.000 EUR erwartete 1T-Steigerung.
- Spieler mit dokumentierter LigaInsider-Spielerseiten-Quote von 0 % werden aus diesen Kacheln ausgeschlossen.

## 0.2.3

- Beim Home-Assistant-Update wird der aktuelle Kickbase-Anwendungscode nun garantiert neu ins Image übernommen.
- Dadurch werden die Ingress-Korrekturen der eingebetteten Oberfläche tatsächlich ausgeliefert.

## 0.2.2

- Home-Assistant-Ingress auf relative Pfade umgestellt, damit die Oberfläche innerhalb des Home-Assistant-Panels geladen wird.
- Kompakten Statuskopf fuer die eingebettete Kickbase-Oberflaeche ergänzt.

## 0.2.1

- Persistente Online-Kalibrierung fuer 1T-Marktwertprognosen ergänzt.
- Vergleich von Prognose und tatsächlicher Marktwertänderung wird lokal gesammelt.
- Die Kalibrierung läuft zunächst im Schattenmodus und verändert keine Empfehlungen.

## 0.2.0

- Zwei konfigurierbare tägliche Vollreport-Zeiten ergänzt.
- E-Mail-Zugangsdaten in die Home-Assistant-App-Konfiguration aufgenommen.
- Dauerhaftes Scheduler-Protokoll ergänzt.
