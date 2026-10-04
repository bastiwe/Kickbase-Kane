# Kickbase-Regelreferenz (Seasonal)

Stand: 2026-10-04. Diese Referenz dient dem Projekt als Quelle fuer
Budget-, Kader- und Bonusberechnungen. Sie fasst ausschliesslich Angaben aus
dem offiziellen Kickbase Help Center zusammen. Nicht veroeffentlichte Werte
sind bewusst nicht geschaetzt.

## Geltungsbereich

Die Regeln hier beziehen sich auf den Seasonal-/Classic-Modus der Bundesliga.
Liga-Admins koennen einzelne Regeln (Kaderlimit, Vereinslimit, Underpay,
Erfolgsboni und Auto-Verkauf) individuell einstellen. Die Live-Daten der
konkreten Liga haben deshalb immer Vorrang.

## Kontostand und 33-Prozent-Regel

Kickbase beschreibt die Grenze als maximal 33 Prozent des Mannschaftswerts
zuzueglich des aktuellen Kontostands. Im offiziellen Beispiel werden bei
100 Mio. EUR Mannschaftswert und -10 Mio. EUR Kontostand 90 Mio. EUR als
Rechenbasis und ein maximales Minus von 30 Mio. EUR genannt.

Wichtig fuer Szenarien im Optimierer:

- Ein Kauf zum Marktwert erzeugt keinen neuen Netto-Wert und darf nicht als
  zusaetzlicher Kreditrahmen behandelt werden.
- Beim Gebot beruecksichtigt Kickbase die Summe aller offenen Gebote, die
  angenommen werden koennten - nicht nur das neu eingegebene Gebot.
- Ein Marktwertanstieg nach der Gebotsabgabe kann bei deaktiviertem Underpay
  dazu fuehren, dass ein vorher ausreichendes Gebot abgelehnt wird.
- Die exakte Pruefung ist serverseitig. Der Optimierer weist daher nur eine
  transparente Naeherung aus und muss aktuelle offene Gebote einbeziehen.

Quellen:

- [33-Prozent-Regel](https://help.kickbase.com/help/wie-weit-darf-ich-ins-minus)
- [Admin-Einstellungen: Underpay](https://help.kickbase.com/en/help/admin-rechte)

## Spieltagsbeginn und Aufstellung

- Zum offiziellen Beginn eines Spieltags muss der Kontostand mindestens
  0 EUR betragen, sonst gibt es keine Punkte fuer den gesamten Spieltag.
- Massgeblich ist die von Kickbase angegebene Startzeit, nicht ein moeglicher
  verspaeteter realer Anpfiff.
- Nach Beginn des ersten Spiels ist die Aufstellung fuer den laufenden
  Spieltag gesperrt.
- Jede unbesetzte Position kostet 100 Punkte.
- Bei Nachholspielen bleibt die Aufstellung vom offiziellen Spieltagsbeginn
  massgeblich; ein zwischenzeitlich verkaufter, damals aufgestellter Spieler
  punktet im Nachholspiel weiter fuer den Manager.

Die detaillierte Wertung einzelner Spielaktionen wird nicht im Projekt
nachgebildet. Sie stammt aus der offiziellen Punktetabelle (ueber 95
Aktionen) und basiert auf Live-Daten von Stats Perform. Relevante Beispiele
sind Startelf (+5), Minutenbonus (+1 je zehn Minuten, plus +1 bei voller
Spielzeit), Sieg (+15), Niederlage (-15) und gelbe Karte (-10). Die echte
realtaktische Position im Spiel, nicht nur die Kickbase-Kaderposition,
bestimmt positionsspezifische Wertungen wie Tore und Zu-Null-Boni.

Quellen:

- [Kontostand und Aufstellung](https://help.kickbase.com/help/regel-4-kontostand-aufstellung)
- [Nachholspiele](https://help.kickbase.com/help/nachholspiele)
- [Offizielle Punktetabelle](https://www.kickbase.com/de/points-table)
- [Erlaeuterung der Punktevergabe](https://en.help.kickbase.com/en/help/how-are-points-calculated-in-kickbase)

## Kader, Vereine und Positionen

- Das Kaderlimit wird vom Liga-Admin festgelegt und kann zwischen 11 und
  25 Spielern liegen. Bei erreichtem Limit ist kein weiterer Kauf moeglich.
- Das Vereinslimit ist ebenfalls eine Ligaeinstellung und kann 1 bis 11
  Spieler je Verein betragen. Ein Gebot wird abgelehnt, wenn der Zuschlag
  das Limit verletzen wuerde.
- Die vier Kickbase-Positionen werden vor der Saison festgelegt. Sie legen
  fest, wo ein Spieler aufgestellt werden darf. Die Punkte richten sich
  dennoch nach seiner realen Position im jeweiligen Spiel.

Quellen:

- [Kaderbegrenzung](https://help.kickbase.com/en/help/kaderbegrenzung)
- [Admin-Einstellungen: Vereinslimit](https://help.kickbase.com/en/help/admin-rechte)
- [Spielerpositionen und Punktevergabe](https://help.kickbase.com/help/spielerposition)

## Markt und Marktwerte

- Der Marktwert wird im Seasonal-Modus taeglich gegen 22:00 Uhr aktualisiert.
- Nachfrage, Form/Leistung sowie erwartete Einsatzzeit beeinflussen ihn.
- Bei deaktiviertem Underpay muessen Gebote mindestens dem Marktwert zum
  Zeitpunkt der Transferabwicklung entsprechen.
- Ein Zuschlag kann trotz Hoechstgebot an Kader- oder Vereinslimit scheitern.

Quellen:

- [Wie wird der Marktwert berechnet?](https://help.kickbase.com/help/kickbase-marktwert)
- [Warum ein Gebot abgelehnt werden kann](https://en.help.kickbase.com/help/i-placed-a-bid-but-didnt-get-the-player)

## Geldboni und Erfolge

Die folgenden wiederholbaren Erfolge und Betraege sind offiziell dokumentiert:

| Bereich | Bedingung | Bonus |
| --- | --- | ---: |
| Spieltag | Spieltagssieger | 1.000.000 EUR |
| Spieltag | mindestens 1.000 / 1.500 / 2.000 Punkte | 250.000 / 500.000 / 1.000.000 EUR |
| Einzelspieler | mindestens 200 / 300 / 400 / 500 Punkte | 100.000 / 500.000 / 1.000.000 / 2.000.000 EUR |
| Spieltag | MVP | 1.000.000 EUR |
| Spieltag | Tormaschine | 250.000 EUR |
| Transfer | 3 / 5 / 10 / 25 Mio. EUR Gewinn mit einem Spieler | 250.000 / 500.000 / 1.000.000 / 2.000.000 EUR |
| Saison | Meister / Vizemeister | 2.000.000 / 1.000.000 EUR |

Regeln dazu:

- Spieltagserfolge sind wiederholbar. Der MVP muss aufgestellt sein; bei
  Punktegleichheit gewinnt der Manager mit dem niedrigeren
  Aufstellungs-Mannschaftswert zum Anpfiff.
- Transfererfolge gelten nur fuer Kauf und anschliessenden Verkauf ueber den
  Transfermarkt, nicht fuer zugeloste Spieler oder Manager-zu-Manager-
  Transfers. Sie setzen die aktuelle Saison voraus.
- Mannschaftswert-Erfolge und "Glueckliches Haendchen" sind einmalig pro
  Liga. Mannschaftswert-Erfolge werden meist gegen 22 Uhr geprueft und
  benoetigen einen positiven Kontostand.
- Spieltagserfolge werden in der Regel am Montagabend gutgeschrieben.
- Ein Liga-Admin kann die Geldboni von Erfolgen deaktivieren. Punktebasierte
  Belohnungen und der taegliche Anmeldebonus bleiben davon unberuehrt.

Quellen:

- [Erfolgsuebersicht](https://help.kickbase.com/help/welche-erfolge-kann-ich-in-der-app-erhalten)
- [Voraussetzungen fuer Transfererfolge](https://help.kickbase.com/help/ich-habe-meinen-erfolg-nicht-erhalten)
- [MVP-Regel](https://help.kickbase.com/help/kickbase-mvp)

## Nicht als Fakt verwenden

Die aktuell eingesehenen offiziellen Seiten nennen keine Staffel oder
Betraege fuer den taeglichen Anmeldebonus und keine vollstaendige Tabelle der
einmaligen Mannschaftswert-Erfolge. Diese Werte duerfen deshalb nicht aus
Vermutungen in die Cash-Schaetzung fliessen. Sie koennen nur beruecksichtigt
werden, wenn sie aus dem Activity Feed, der eigenen Erfolgsansicht oder einer
weiteren offiziellen Kickbase-Quelle konkret nachweisbar sind.

## Projektregel fuer Berechnungen

1. API-/Activity-Feed-Buchungen sind Ist-Werte und haben Vorrang.
2. Offiziell dokumentierte, aus den API-Daten eindeutig ableitbare Boni
   duerfen als getrennte Prognoseposition erscheinen.
3. Nicht beobachtbare Erfolge, Login-Boni oder Admin-Gutschriften werden
   nicht als sicherer Cash-Bestand behauptet.
4. Jede Cash- oder Kaufkraftanzeige muss als Schaetzung mit Datenzeitpunkt,
   offenen Geboten und den beruecksichtigten Annahmen ausgewiesen werden.
