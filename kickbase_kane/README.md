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
  `21:40,22:10`
- optional `openai_api_key` und `openai_model` fuer den KI-Berater

Danach **Speichern** und die App einmal neu starten. Der Vollreport wird zu jeder
konfigurierten Uhrzeit ausgefuehrt. Laufende und vergangene Ausfuehrungen stehen
im App-Protokoll; das dauerhafte Detail-Log liegt unter
`/data/scheduled-report.log`.

Marktwertcache, Berichte, SQLite-Datenbank, gespeicherte Aufstellungen und lokale
KI-Hinweise liegen dauerhaft im Add-on-Datenordner. Der Startelf-Optimierer und
die Report-Ansicht bleiben ueber die Kickbase-App in Home Assistant erreichbar.
