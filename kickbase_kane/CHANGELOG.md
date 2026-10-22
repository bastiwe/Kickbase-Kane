# Changelog

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
