# Kickbase Kane fuer Home Assistant OS

Das Add-on betreibt das private Kickbase-Dashboard innerhalb von Home Assistant.
Es nutzt Ingress: Zugriff erfolgt ausschliesslich ueber Home Assistant und dessen
Benutzeranmeldung; es wird kein eigener Port am Router freigegeben.

## Dashboard individuell gestalten

Ab Version **0.2.81** öffnet **Dashboard bearbeiten** den Editor. Links lassen sich
Rasterspalten, Zeilenhöhe und Abstand einstellen sowie leere Kacheln oder
Spieler-Blueprints hinzufügen. Kacheln am Titelgriff ziehen und am grünen Eckgriff
skalieren. Bei überlappenden Kacheln weichen die anderen Kacheln nach unten aus.

Rechts zeigt die ausgewählte Kachel ihre Elemente und Eigenschaften. Text-, Daten-
und Bildelemente lassen sich hinzufügen, direkt verschieben und am blauen Eckgriff
skalieren. Farbe, Schriftgröße, Deckkraft, Rundung, Bildausschnitt und Position
können auch exakt eingestellt werden. **Nach vorne / Nach hinten** legt fest,
welche Elemente sich überdecken. Ein Wappen als Bildelement mit 5 % Deckkraft und
voller Kachelgröße eignet sich beispielsweise als Hintergrund.

Der Quellen-Wähler durchsucht alle Felder des aktuell geladenen Dashboard-Reports
und die verfügbaren API-Antworten für Managerbudgets, Transfers, Kaderwertverlauf
und Aufstellung. Unter **Dashboard-Kennzahlen** stehen auch die berechneten Summen
für Kaderwert, Kadergröße und erwartete Marktwertänderung bereit.
Zusätzliche Spielerdetails und Marktwertverläufe lassen sich für
den ausgewählten Spieler laden; gespeicherte Bindungen laden diese Daten beim
Anzeigen wieder nach. **Quelle zuweisen** verbindet das ausgewählte Daten- oder
Bildelement mit einem Feld. **+ Datenelement** erstellt ein neues Element.
Bei Spieler-Blueprints beziehen sich die Quellen unter **Gewählter Datensatz**
auf die Spieler-ID, auch wenn die Kaderliste später anders sortiert ist. Fehlende
Werte erscheinen als „–“, fehlende Bilder als Platzhalter. Ohne Live-Zugang
bleiben die Reportdaten nutzbar; zusätzliche API-Quellen sind dann nicht verfügbar.

Grafiken können über HTTPS-Adressen oder per Upload eingebunden werden. Uploads
werden auf maximal 1000 Pixel verkleinert und platzsparend im Layout hinterlegt
(GIFs als Einzelbild). Eine Bilddatei darf beim Upload höchstens 10 MB groß sein;
das gespeicherte Layout darf insgesamt 1,8 MB und 80 Kacheln je Ansicht enthalten.

Über **Desktop / Mobil** zwei unabhängige Layouts bearbeiten. Die Vorschaubreite
simuliert das Gerät; das Dashboard verwendet unter 900 Pixeln automatisch das
Mobil-Layout. **Andere Ansicht übernehmen** kopiert bei Bedarf ein Layout, danach
kann dessen Raster angepasst werden. **Vorschau** blendet Bearbeitungsgriffe aus.

**Mein Layout im Dashboard verwenden** aktivieren und **Speichern** drücken.
Gespeichert werden immer beide Ansichten; ohne Speichern bleibt es ein Entwurf.
Das Layout liegt in `/data/.advisor-dashboard-layout.json` und übersteht Neustarts
und Add-on-Updates. Es gilt für dieses Add-on und alle zugreifenden Geräte.
**Standardansicht** im Dashboard schaltet vorübergehend zur bisherigen Ansicht.
Export/Import sichert das Layout als JSON-Datei; Import wird erst mit Speichern
übernommen. Rückgängig/Wiederholen gilt für Änderungen seit dem letzten Speichern.
Bei einem Speicherkonflikt zuerst den Entwurf exportieren und die Seite neu laden.

## Einrichtung

Nach Installation in Home Assistant unter **Einstellungen -> Apps -> Kickbase Kane
-> Konfiguration** eintragen:

- `kick_user` und `kick_pass`: Kickbase-Zugang
- `league_name`: exakter Name der Kickbase-Liga
- `email_user` und `email_pass`: Gmail-Adresse und App-Passwort fuer die
  automatischen Report-Mails
- `report_times`: Berliner Uhrzeiten als kommagetrennte Liste, standardmaessig
  `06:30,14:00,22:10`
- optional `openai_api_key` und `openai_model` fuer den KI-Berater

Danach **Speichern** und die App einmal neu starten. Der Vollreport wird zu jeder
konfigurierten Uhrzeit ausgefuehrt. Laufende und vergangene Ausfuehrungen stehen
im App-Protokoll; das dauerhafte Detail-Log liegt unter
`/data/scheduled-report.log`.

Der Timer läuft direkt im HA-Add-on, auch wenn der GitHub-Prognose-Sync aktiv ist.
Mit `github_forecast_token` fordert er zu den drei Uhrzeiten den Vollreport-Workflow
direkt in GitHub an; Berechnung und Mailversand nutzen dann die dort hinterlegten
Secrets. Der Token benötigt für das Repository **Actions: Read and write**.
Ohne Token wird der Vollreport lokal berechnet und nutzt die E-Mail-Zugangsdaten
des Add-ons. Die Uhrzeiten sind Startzeiten; die Mail folgt nach der Berechnung.

Sommer- und Winterzeit werden über `Europe/Berlin` berücksichtigt. Das Add-on muss
laufen. Nach einem kurzen Neustart wird ein verpasster Termin bis zu 15 Minuten
nachgeholt. Fehlgeschlagene Startversuche werden höchstens dreimal im Abstand von
fünf Minuten wiederholt. Angenommene Starts werden dauerhaft protokolliert, um sie
nach einem Neustart nicht erneut auszulösen. Ein angenommener GitHub-Start bestätigt
die Anforderung, nicht den erfolgreichen Abschluss des Reports.

Beim Update wird der bisherige Standard `21:40,22:10` automatisch auf die neuen
drei Termine umgestellt. Andere selbst gesetzte Zeiten bleiben erhalten; dafür
`report_times` bei Bedarf auf `06:30,14:00,22:10` setzen. Das Update installieren
und das Add-on neu starten. Der GitHub-Cron kann zusätzlich weiterhin Reports auslösen.

Marktwertcache, Berichte, SQLite-Datenbank, gespeicherte Aufstellungen und lokale
KI-Hinweise liegen dauerhaft im Add-on-Datenordner. Der Startelf-Optimierer und
die Report-Ansicht bleiben ueber die Kickbase-App in Home Assistant erreichbar.
