# Changelog

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

# Changelog

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
