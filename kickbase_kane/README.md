# Kickbase Kane fuer Home Assistant OS

Das Add-on betreibt das private Kickbase-Dashboard innerhalb von Home Assistant.
Es nutzt Ingress: Zugriff erfolgt ausschliesslich ueber Home Assistant und dessen
Benutzeranmeldung; es wird kein eigener Port am Router freigegeben.

Nach der Installation werden Kickbase-Zugang, Liga und optional der OpenAI-Key
in der Add-on-Konfiguration hinterlegt. Marktwertcache, Berichte, SQLite-Datenbank,
gespeicherte Aufstellungen und lokale KI-Hinweise liegen dauerhaft im Add-on-Datenordner.
Der Vollreport laeuft taeglich zur konfigurierten Berliner Uhrzeit (Standard `22:15`).
