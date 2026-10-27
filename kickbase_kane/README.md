# Kickbase Kane fuer Home Assistant OS

Das Add-on betreibt das private Kickbase-Dashboard innerhalb von Home Assistant.
Es nutzt Ingress: Zugriff erfolgt ausschliesslich ueber Home Assistant und dessen
Benutzeranmeldung; es wird kein eigener Port am Router freigegeben.

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
