# Kickbase Kane fuer Home Assistant OS

Das Add-on betreibt das private Kickbase-Dashboard innerhalb von Home Assistant.
Es nutzt Ingress: Zugriff erfolgt ausschliesslich ueber Home Assistant und dessen
Benutzeranmeldung; es wird kein eigener Port am Router freigegeben.

## Dashboard individuell gestalten

**Dashboard bearbeiten** öffnet den Editor. Ab Version **0.2.82** startet ein neues
Layout mit den fünf Hauptbereichen des bestehenden Dashboards: **Letzte Transfers**,
**Beste Chancen vor MW-Update**, **Wertentwicklung**, **Handlungsbedarf** und
**Transfermarkt**. Kennzahlen, Kaderwertgrafik und Managerbudgets bleiben im
Dashboard erhalten.

Pro Hauptbereich wird genau **eine Spielerkachel als Vorlage** bearbeitet,
unabhängig davon, wie viele Spieler gerade vorhanden sind. Der Editor zeigt
Platzhalter statt konkreter Spieler. Das Dashboard wiederholt die Vorlage später
für alle passenden Datensätze. Ein vorhandenes freies Layout bleibt erhalten;
**Bestehendes Dashboard als Vorlage** ersetzt die aktuell bearbeitete Ansicht
erst als Entwurf. Zum Umstellen beide Ansichten laden und anschließend speichern.

Links lassen sich Rasterspalten, Zeilenhöhe und Abstand der Hauptbereiche
einstellen. Bereiche am Titelgriff ziehen und am grünen Eckgriff skalieren.
Rechts legt **Spielerkacheln je Zeile** das Raster innerhalb des ausgewählten
Bereichs fest. **Spielerkachelhöhe** und **Spielerkachelabstand** gelten für alle
Spieler dieses Bereichs. Diese Einstellungen sind für Desktop und Mobil getrennt.
Bei neuen oder entfernten Datensätzen ändern sich Kachelanzahl und Bereichshöhe
automatisch; folgende Bereiche weichen nach unten aus.

Rechts zeigt die ausgewählte Kachel ihre Elemente und Eigenschaften. Text-, Daten-
und Bildelemente lassen sich hinzufügen, direkt verschieben und am blauen Eckgriff
skalieren. Farbe, Schriftgröße, Deckkraft, Rundung, Bildausschnitt und Position
können auch exakt eingestellt werden. **Nach vorne / Nach hinten** legt fest,
welche Elemente sich überdecken. Ein Wappen als Bildelement mit 5 % Deckkraft und
voller Kachelgröße eignet sich beispielsweise als Hintergrund.

Bei einer Bereichsvorlage stehen im Quellen-Wähler benannte Platzhalter bereit,
etwa **Name**, **Nachname**, **Vereinswappen**, **Spielerbild**, **Position**,
**Marktwert**, **Erw. 1T**, **LI**, **Status**, **Durchschnittspunkte** und **Form 1–3**.
Für Transfers gibt es zusätzlich Bezahlt, Verkäufer, Käufer, Overpay und G/V des
Verkäufers. Unter **Weitere Spielerdaten** sind zusätzliche Felder der aktuell
verfügbaren Datensätze zugänglich. Jeder Platzhalter wird mit den Daten der
jeweiligen Spielerkachel gefüllt; es wird keine feste Spieler-ID gespeichert.
**Quelle zuweisen** bindet ein vorhandenes Element, **+ Datenelement** erstellt
ein neues. Unter **Dashboard-Kennzahlen** stehen auch die berechneten Summen
bereit. Freie zusätzliche Kacheln können weiterhin auf die kompletten aktuellen
Report- und API-Antworten zugreifen. Fehlende Werte erscheinen als „–“.

Die Datenzuordnung folgt den Bereichen: Transfers stammen aus dem Live-Feed,
Wertentwicklung enthält den Kader, Transfermarkt die vorhandenen Marktangebote.
Beste Chancen enthält Angebote mit mindestens 100.000 € erwarteter Steigerung
und Ablauf vor dem nächsten Berliner MW-Update um 22 Uhr. Handlungsbedarf zeigt
negative Kaderprognosen und passende Angebote bis zur folgenden Nacht-/Morgenphase.
Es gibt keine feste Anzahl gespeicherter Spielerkacheln und keine zusätzlichen
Kachel-Limits im Renderer; der Transfer-Feed liefert aktuell die fünf neuesten
Transfers. Bei Verkäufen an Kickbase wird Overpay ausgeblendet und stattdessen
G/V angezeigt. Der Transfer-Marktwert bleibt der damalige Wert. Form 1 ist der
neueste Spieltag; vorhandene Nullpunkte werden erhalten.

Grafiken können über HTTPS-Adressen oder per Upload eingebunden werden. Uploads
werden auf maximal 1000 Pixel verkleinert und platzsparend im Layout hinterlegt
(GIFs als Einzelbild). Eine Bilddatei darf beim Upload höchstens 10 MB groß sein;
das gespeicherte Layout darf insgesamt 1,8 MB und 80 Kacheln je Ansicht enthalten.

Über **Desktop / Mobil** zwei unabhängige Layouts bearbeiten. Die Vorschaubreite
simuliert das Gerät; das Dashboard verwendet unter 900 Pixeln automatisch das
Mobil-Layout. **Andere Ansicht übernehmen** kopiert bei Bedarf ein Layout, danach
kann dessen Raster angepasst werden.

**Vorschau** zeigt ab Version **0.2.83** das vollständige Dashboard mit echten
Spielerdaten, Spielerbildern, Wappen und allen passenden Spielerkacheln. Verwendet
wird der aktuelle Entwurf, auch wenn er noch nicht gespeichert oder aktiviert
ist. Desktop/Mobil und die Vorschaubreite lassen sich weiterhin umschalten.
Die Vorschau lädt dieselben aktuellen Report-/API-Daten und verwendet dieselben
Stile und Renderer wie das Dashboard. Ohne Live-Zugriff bleiben die vorhandenen
Reportdaten nutzbar; nicht verfügbare Werte erscheinen wie im Dashboard als „–“.
**Zurück zum Bearbeiten** erhält die ungespeicherten Änderungen. Die Vorschau
speichert nichts automatisch und erlaubt keine Reportstarts oder Navigation
über Dashboard-Aktionsschaltflächen.

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
