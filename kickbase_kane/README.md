# Kickbase Kane fuer Home Assistant OS

Das Add-on betreibt das private Kickbase-Dashboard innerhalb von Home Assistant.
Es nutzt Ingress: Zugriff erfolgt ausschliesslich ueber Home Assistant und dessen
Benutzeranmeldung; es wird kein eigener Port am Router freigegeben.

## Dashboard individuell gestalten

**Dashboard bearbeiten** öffnet ab Version **0.2.84** die tatsächliche
Standardansicht mit ihren vorhandenen Kacheln und CSS-Stilen. Bearbeitbar sind
**Verfügbares Budget**, **Kaderwert**, **Erw. Kader-MW in 1T**, die
**Kaderwertgrafik**, **Managerbudgets** und die fünf Spielerbereiche
**Letzte Transfers**, **Beste Chancen vor MW-Update**, **Wertentwicklung**,
**Handlungsbedarf** und **Transfermarkt**. Ohne Anpassungen verwendet die Vorschau
bei gleicher Breite das unveränderte Originaldesign.

Je Spielerbereich erscheint im Bearbeitungsmodus genau **eine Beispielkachel**
mit echten Daten, Spielerbild und Vereinswappen. Sie ist keine Bindung an einen
bestimmten Spieler: Änderungen an Bildposition, Größe, Schrift oder Farben gelten
für alle Spieler dieses Bereichs. Wenn ein Bereich gerade leer ist, zeigt der
Bearbeitungsmodus nach Möglichkeit einen Spieler aus dem vorhandenen Kader oder
Markt als Gestaltungsmuster. Die Vorschau zeigt anschließend die tatsächlich
passenden Datensätze; Datenfilter und Sortierung entsprechen der Standardansicht.

Ein Element direkt anklicken oder rechts in der Elementliste auswählen. Elemente
lassen sich am Auswahlrahmen verschieben und am Eckgriff skalieren. Bildversatz
wird relativ zur vorhandenen Position eingestellt, Breite/Höhe in Prozent der
Originalgröße (100 %). Auch Schrift, Deckkraft, Hintergrund, Bildausschnitt und
Rundung können exakt eingestellt werden. Weitere Text-, Daten- und Bildelemente
lassen sich hinzufügen und werden bei Spielerbereichen automatisch wiederholt.
Die vorhandenen Datenverknüpfungen bleiben erhalten, solange du sie nicht änderst.

Hauptkacheln am Titelgriff nach oben/unten verschieben oder ihre Reihenfolge und
Breite rechts einstellen. Erst wenn eine solche Layoutänderung erfolgt, werden
die Originalkacheln in einem gemeinsamen Raster angeordnet. Unveränderte Bereiche
behalten zunächst ihr bestehendes Layout. Über **Spielerkacheln je Zeile** und
**Spielerkachelabstand** lässt sich das innere Raster eines Spielerbereichs
anpassen. Die Mindesthöhe kann ebenfalls eingestellt werden. Beim Transfermarkt
wandelt eine explizite Rasteranpassung die bisherigen Tabellenzeilen in Kacheln um.

Benannte Datenquellen wie **Vereinswappen**, **Spielerbild**, **Position**,
**Marktwert**, **Erw. 1T**, **LI**, **Status** und **Durchschnittspunkte** werden
je Spieler befüllt. Für Kennzahlen stehen unter **Dashboard-Kennzahlen** die
berechneten Summen bereit. **Quelle zuweisen** verbindet ein vorhandenes Element,
**+ Datenelement** ergänzt ein neues. Bei Kickbase-Verkäufen bleibt G/V statt
Overpay erhalten; der Transfer-Marktwert bleibt der damalige Wert.

Ältere freie Layouts bleiben beim Update gespeichert. Im Editor wird zunächst
die vollständige Standardansicht als ungespeicherter Entwurf angeboten;
**Rückgängig** bringt den bisherigen Stand zurück. Erst **Speichern** ersetzt
ihn. **Standardansicht exakt übernehmen** setzt die aktuell bearbeitete Ansicht
auf das Original zurück, ebenfalls zuerst als rückgängig machbaren Entwurf.

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

## Spielerdetails im Startelfplaner

Ein Klick auf das Spielerbild öffnet die Detailansicht, sowohl in Startelf und Bank
als auch im Auswahlfenster für einen freien Platz. Der Bildklick verändert die
Aufstellung nicht. Im Auswahlfenster übernimmt ein Klick auf die übrige Kachel den
Spieler; eine zusätzliche Spalte zeigt seine nächsten drei Gegner mit Tabellenplatz,
Heim-/Auswärtsangabe und Termin.

Die Detailansicht zeigt verfügbare Kickbase-Daten zu Performance, Marktwertverlauf,
Punkten, Minuten, Toren, Vorlagen und Karten sowie die vorhandene Erw.-1T-Prognose
und G/V. Leistungsbalken lassen sich für Spieldetails anklicken oder antippen.
Marktwertzeiträume und die Ansicht der letzten acht Spiele bzw. der aktuellen
Saison sind umschaltbar. Desktop verwendet drei Spalten, mobil stehen die Bereiche
kompakt untereinander. Fehlende Werte erscheinen als „–“; nicht abrufbare Live-Daten
werden kenntlich gemacht. Die Ansicht benötigt keine zusätzlichen API-Schlüssel.

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
