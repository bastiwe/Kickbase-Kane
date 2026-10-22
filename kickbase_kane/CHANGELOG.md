# Changelog

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
