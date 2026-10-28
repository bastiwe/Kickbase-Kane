# Changelog

## 0.2.88

- Ersetzt die feste 5-Mio.-Minus-Option im Startelfplaner durch ein frei wählbares erlaubtes Minus in Euro mit Übernehmen-Button. Der Startwert bleibt 5 Mio. €; 0 € erlaubt kein Minus.
- Berücksichtigt die bestätigte Grenze bei Formationsfarben, vorgeschlagenen Aufstellungen und „Beste Elf“. Zeigt die aktuell aktive Grenze unter der Eingabe an; unbestätigte Eingaben verändern die Berechnung nicht.

## 0.2.87

- Zeigt im Startelfplaner fünf Startelfsymbole im Kickbase-Stil mit LI-Prozentwert im Tooltip: Sicher ab 80 %, Erwartet ab 65 %, Unsicher ab 25 %, Unwahrscheinlich über 0 % und Ausgeschlossen bei 0 %.
- Ergänzt unter dem Spielerstatus auf Startelf- und Bankkacheln eine kompakte Zeile mit Erw. 1T-Prognose und Gewinn/Verlust nebeneinander, ohne die Kacheln zu verbreitern.

## 0.2.86

- Hält die Restbudgetkachel im mobilen Startelfplaner beim Scrollen wieder unter der Kopfzeile sichtbar.
- Zeigt hinter jeder Formation in Klammern die Summe der Durchschnittspunkte ihrer vorgeschlagenen Startelf. Die Punkte beziehen sich auf die unter Berücksichtigung der Budgetgrenze ausgewählten Spieler.

## 0.2.85

- Wählt im Startelfplaner die punktestärkste vollständige Elf innerhalb der erlaubten Budgetgrenze und übernimmt diese beim Anklicken einer Formation.
- Zeigt Formationen nur gelb, wenn keine vollständige Elf die Budgetgrenze erreicht. Mit „Bis 5 Mio. € Minus erlauben“ sind Endbudgets ab -5 Mio. € grün, andernfalls ab 0 €.
- Berücksichtigt fixierte Startelfspieler, gehaltene Spieler und simulierte Käufe bei der Budgetprüfung; simulierte Käufe werden nicht als mögliche Verkaufserlöse gerechnet.

## 0.2.84

- Bearbeitet die tatsächliche Standardansicht mit ihren vorhandenen HTML-Kacheln und CSS-Stilen, einschließlich Budget, Kaderwert, Kaderprognose, Kaderwertgrafik und Managerbudgets. Unveränderte Vorlagen erhalten das Originaldesign.
- Zeigt je Spielerbereich genau eine Beispielkachel mit echtem Spielerbild und Vereinswappen zum Ausrichten. Positions-, Größen-, Schrift- und Farbänderungen gelten für alle Spieler dieses Bereichs.
- Unterstützt Auswählen, Ziehen und Skalieren direkt in der Standardansicht sowie zusätzliche Text-, Daten- und Bildelemente. Desktop-/Mobilansichten bleiben getrennt; Desktop startet mit der tatsächlichen Maximalbreite von 1.480 px.
- Öffnet ältere freie Layouts zunächst als reversible Standardansicht-Entwürfe. Der gespeicherte Stand bleibt bis zum ausdrücklichen Speichern erhalten und ist über Rückgängig erreichbar.

## 0.2.83

- Zeigt im Editor eine echte Vorschau des vollständigen Dashboards mit aktuellen Report-/API-Daten, Spielerbildern, Vereinswappen und allen passenden Spielerkacheln.
- Verwendet dabei den ungespeicherten Entwurf und die ausgewählte Desktop-/Mobilansicht in der eingestellten Vorschaubreite; Speichern oder Aktivieren ist dafür nicht nötig.
- Erhält den Entwurf beim Zurückwechseln zum Bearbeiten. Bearbeitungsleisten und schreibende Dashboard-Aktionen sind in der Vorschau ausgeblendet.

## 0.2.82

- Bietet das bestehende Dashboard mit den fünf Hauptbereichen Letzte Transfers, Beste Chancen vor MW-Update, Wertentwicklung, Handlungsbedarf und Transfermarkt als Editor-Vorlage an.
- Bearbeitet pro Hauptbereich genau eine Spielerkachel mit selbsterklärenden Platzhaltern wie Spielerbild, Vereinswappen, Marktwert, Erw. 1T und LI; das Design gilt automatisch für alle passenden Datensätze.
- Ermöglicht getrennte Spielerkachelraster je Hauptbereich und Desktop-/Mobilansicht. Anzahl und Bereichshöhe passen sich den aktuellen Report- und API-Daten an.
- Erhält die bisherigen Kennzahlen, Kaderwertgrafik und Managerbudgets. Vorhandene freie Layouts werden nicht überschrieben und lassen sich im Editor gezielt durch die Dashboard-Vorlage ersetzen.

## 0.2.81

- Ergänzt einen Dashboard-Editor mit getrennten Desktop- und Mobil-Layouts, anpassbarem Kachelraster und Ziehen zum Verschieben und Skalieren von Kacheln und Elementen.
- Bietet Text-, Daten- und Bildelemente, Spieler-Blueprints mit Porträts und Wappen, Bild-Upload, Farben, Deckkraft, Schriftgrößen und Ebenenreihenfolge.
- Macht alle Felder des aktuellen Dashboard-Reports und die verfügbaren Live-Daten aus Managerbudgets, Transfers, Aufstellung, Marktwertverläufen und Spielerdetails als durchsuchbare Quellen nutzbar.
- Speichert beide Ansichten dauerhaft im Add-on, inklusive Export/Import, Vorschau, Rückgängig/Wiederholen und Schutz vor gleichzeitigem Überschreiben. Die Standardansicht bleibt umschaltbar.

## 0.2.80

- Verkleinert die Porträts leicht, sodass etwas Trikokragen sichtbar wird; die Skalierung ist oben verankert und verschiebt die Köpfe nicht nach unten.

## 0.2.79

- Reduziert die Vereinswappen im Kachelhintergrund auf 5 % Deckkraft.
- Vergrößert den Kopfbereich der Spielerporträts deutlich und positioniert ihn höher im Kreis, sowohl in Startelf- als auch Bankkacheln.

## 0.2.78

- Zentriert die Desktop-Positionsreihen mit kompakteren Abständen zwischen den Spielerkacheln.
- Vergrößert den Porträt-Zoom und verwendet das vergrößerte Vereinswappen mit 20 % Deckkraft als angeschnittenen Hintergrund der Startelf- und Bankkacheln.

## 0.2.77

- Zeigt den grünen Halten-Rand auch bei Startelfspielern im mobilen und Desktop-Startelfplaner; die Markierung wird beim Aufheben wieder entfernt.

## 0.2.76

- Verwendet die Desktop-Matchday-Kacheln auch im mobilen Startelfplaner und auf der Bank, als einspaltige Liste über die verfügbare Displaybreite.
- Optimiert mobile Schriftgrößen, Budgetanzeige und Bedienelemente; Verkauf und Halten bleiben per Wischgeste steuerbar.

## 0.2.75

- Strafft die Vollreport-Mail: entfernt höchste Kaufkraft, Cash-Basis, Cash-/Erfolgsprotokoll, interne Spieler-IDs und Legende; zeigt LI direkt neben Status.
- Berechnet die beste Startelf mit der Bewertung des HA-Planers und mindestens 0 € Restbudget nach Bankverkäufen über alle Formationen.
- Entfernt den Optimierer-Anhang aus der Vollreport-Mail; seine Daten bleiben intern für Kaderanalyse und HA-Sync verfügbar.

## 0.2.74

- Startet Vollreports täglich um 06:30, 14:00 und 22:10 Uhr (Europe/Berlin) über den HA-Addon-Timer.
- Aktiviert den Timer auch mit GitHub-Sync: Reports werden direkt per Workflow-Dispatch angefordert, ohne GitHub-Token lokal berechnet.
- Ergänzt persistente Startprotokolle, begrenzte Wiederholungen und 15 Minuten Nachholzeit nach kurzen Neustarts.
- Migriert den bisherigen Standardzeitplan automatisch und dokumentiert die erforderlichen GitHub-Tokenrechte.

## 0.2.73

- Vergibt bei Torgleichstand für Tormaschine die volle Prämie von 250.000 € an alle Manager mit der höchsten positiven Startelf-Torzahl, unabhängig von ihren Managerpunkten.
- Berechnet die Erfolgsboni und Kontostandsschätzungen vergangener Spieltage entsprechend neu.

## 0.2.72

- Ruft historische Startaufstellungen, Spielerpunkte und Torereignisse je Manager und Spieltag direkt aus dem Kickbase-Teamcenter ab.
- Prüft Spielerlisten und Punktesumme gegen die finalen Managerpunkte und archiviert die API-Belege dauerhaft.
- Berechnet Erfolgsboni und geschätzte Managerkontostände für alle abgeschlossenen Spieltage neu; Rekonstruktionen dienen nur noch als gekennzeichneter Ersatz bei fehlenden API-Daten.

## 0.2.71

- Berücksichtigt für MVP und Tormaschine ausschließlich die aktive Startelf zum Spieltagsbeginn; Bankspieler lösen keine Spieltagsboni aus.
- Übernimmt die vom Nutzer bestätigten Bankspieler von Johannes und Sebastian für Spieltag 7 als gesonderten historischen Beleg.
- Lässt Tormaschine bei uneindeutigen Torzahlen der rekonstruierten Startelf offen und zählt Spieler-Punktestufen weiterhin höchstens einmal pro Manager.

## 0.2.70

- Wertet die montägliche Kickbase-Ranglistenveröffentlichung als verbindlichen Abschluss eines Spieltags, auch wenn die Manager-API ihn weiterhin als `cur` markiert.
- Bezieht dadurch finale Punkte, Spieltagssieg, Punkteboni und Saisonmeilensteine in die Cash-Rekonstruktion ein.
- Nutzt für Spieler-Punkteerfolge, MVP und Tormaschine weiterhin den zum Freitagsspiel fixierten Kader; fehlt ein historischer Snapshot, bleibt die Rekonstruktionsbasis sichtbar.

## 0.2.69

- Berücksichtigt in der Formanzeige stets die letzten drei Bundesliga-Spieltage und zeigt einen Spieltag ohne Einsatz als 0 Punkte an.

## 0.2.68

- Kennzeichnet den nächsten Gegner auf den Matchday-Karten mit H oder A für Heim- und Auswärtsspiele.
- Liest die letzten drei Kickbase-Punktwerte in der korrekten Reihenfolge (aktuellstes Spiel zuerst).
- Vergrößert die Spielerbilder im runden Porträtbereich für besser erkennbare Gesichter.
- Verwendet die vertikalen Matchday-Karten auch für Bankspieler und integriert auf Desktop die Aktionen Verkauf und Halten; mobil bleiben die Wischgesten erhalten.

## 0.2.67

- Ersetzt die bisherigen Desktop-Spielfeldkarten durch kompakte, vertikale Matchday-Karten nach der gelieferten Referenz.
- Zeigt Spielerfoto, Startelfindikator, Nachname, nächsten Gegner samt Tabellenplatz, Durchschnittspunkte, Marktwert, Status und die letzten drei Spiele (neuestes oben).

## 0.2.66

- Übernimmt die bewährte Bild-/Wappenkomposition der Platzauswahl unverändert für Desktop-Startelfkarten.
- Verhindert beim Fixieren eines bereits aufgestellten Spielers eine Neuberechnung und Umsortierung der Startelf.

## 0.2.65

- Richtet Spielerbild und Vereinswappen auf Desktop-Startelfkarten weiter links wie in „Letzte Transfers“ aus.
- Liest den sichtbaren Managernamen aus der Kickbase-Transferhistorie, sodass Verkäufe an Kickbase ihr G/V ausweisen.

## 0.2.64

- Fixiert Marktwert und Overpay der letzten Transfers auf den Wert zum Transferzeitpunkt.
- Zeigt bei Verkäufen an Kickbase den Gewinn oder Verlust des Verkäufers statt eines bedeutungslosen Overpays.
- Führt eine eigenständige, kompaktere Kartenkomposition für Smartphones ein.
- Verkleinert Bildfläche und Kartenhöhe im Startelfplaner, ohne Spieler und Vereinswappen zu trennen.
- Gibt Namen und Kennzahlen in der mobilen Wertentwicklung durch gestapelte Inhalte wieder ausreichend Platz.
- Strafft mobile Transfermarktkarten und erhält die vertikale, überlauffreie Darstellung.

## 0.2.63

- Rückt Spieler und Vereinswappen in der gemeinsamen Kartenkomposition etwas nach rechts, sodass die Spielergesichter vollständig sichtbar bleiben.
- Hebt das Wappen hinter dem Spieler wieder leicht an, bis es beinahe den oberen Kachelrand erreicht.
- Vergrößert die reservierten Textabstände passend zur verschobenen Grafik und stapelt mobile Transferwerte bei Bedarf.

## 0.2.62

- Zieht das übergroße Vereinswappen in der gemeinsamen Bildkomposition weiter nach unten hinter den Spieler.
- Überträgt die halb angeschnittene Wappen-Spieler-Komposition auf Wertentwicklung, Handlungsbedarf und Transfermarkt.
- Vereinheitlicht Startelf-, Bank- und Auswahlkacheln im Startelfplaner mit derselben Bildsprache und getrennten Textflächen.
- Behält für schmale Ansichten eigene Abstände und Größen bei, damit kein horizontaler Seitenüberlauf entsteht.

## 0.2.61

- Verdoppelt Wappen und Spielerbild in „Letzte Transfers“ und „Beste Chancen vor MW-Update“.
- Vergrößert den reservierten Bildbereich, damit die deutlich größere Komposition nicht mit den Texten kollidiert.
- Wechselt bei schmaleren Ansichten früher auf eine einzelne Transferkachel pro Reihe.

## 0.2.60

- Repariert das Layout von „Beste Chancen vor MW-Update“ mit einer eigenen, stabilen Inhaltsstruktur.
- Schiebt Wappen und Spieler in „Letzte Transfers“ sowie „Beste Chancen“ jeweils ungefähr zur Hälfte links aus der Kachel.
- Vergrößert das Wappen deutlich und hält den Spieler als vordere Ebene klar davor.
- Reserviert rechts neben dem sichtbaren Bildausschnitt ausreichend Platz für Namen, Werte und Ablaufdaten.
- Zeigt „Letzte Transfers“ auf Desktop in maximal drei deutlich breiteren Kacheln pro Reihe statt fünf schmalen Spalten.

## 0.2.59

- Ordnet Spielerbild und Vereinswappen in „für freien Platz wählen“ nach der gelieferten Referenz neu an.
- Reserviert links einen hohen, angeschnittenen Bildbereich mit vollhohem Wappen im Hintergrund und vollhohem Spieler davor.
- Übernimmt diese Bildkomposition auch in Startelf-, Bank-, Dashboard- und Transferkacheln.
- Trennt Bildbereich, Texte, Werte und Buttons räumlich, sodass keine Beschriftung die Bilder überlappt.
- Behält Statistiken und Budgetberechnung unverändert bei und passt die Bildfläche für schmale Mobilansichten separat an.

## 0.2.58

- Skaliert das Vereinswappen über die vollständige Höhe der jeweiligen Spielerkachel.
- Verankert das freigestellte Spielerbild am unteren Kachelrand und begrenzt es auf ungefähr die halbe Kachelhöhe.
- Legt Spielerinformationen auf leicht transparente, weichgezeichnete Flächen über die Grafik, damit alle Werte lesbar bleiben.

## 0.2.57

- Sichert das bisherige Spielerkachellayout als Git-Tag `backup/player-card-layout-0.2.56`.
- Nutzt das Vereinswappen groß und dezent transparent als Hintergrund der Spielerabbildung.
- Zeigt das freigestellte Spielerbild rahmenlos davor und skaliert es auf ungefähr zwei Drittel der Wappenhöhe.
- Reicht Vereinswappen aus Kickbase-Livedaten und dem Spieler-Cache bis in Startelfplaner, Dashboard und Transferhistorie durch.

## 0.2.56

- Stellt den Transfermarkt auf Mobilgeräten als kompakte Karten statt als breite Desktop-Tabelle dar.
- Verhindert horizontales Scrollen durch eine vollständig flexible Tabellenbreite und gekürzte lange Spielernamen.
- Blendet die Marktwert-Detailzeile mobil wieder korrekt aus, bis ein Spieler aktiv aufgeklappt wird.

## 0.2.55

- Zeigt im Trading Dashboard die fünf neuesten Liga-Transfers live aus dem Kickbase-Aktivitätenfeed.
- Ergänzt Spielerbild, Transferweg, bezahlten Preis, damaligen Marktwert und zeitlichen Abstand zum Transfer.
- Berechnet den Overpay als gezahlten Preis abzüglich Marktwert zum Transferzeitpunkt; fehlende Werte werden aus der Kickbase-Marktwerthistorie ergänzt.

## 0.2.54

- Synchronisiert neben der MW-Prognose nun auch den vollständigen Dashboard-Report aus dem GitHub-Vollreport ins Add-on.
- Übernimmt dadurch LI-Startelfwahrscheinlichkeiten aus demselben Datenstand, der bereits im Mailreport angezeigt wird.
- Lädt einen neu synchronisierten Dashboard-Report beim nächsten Seitenaufruf ohne Add-on-Neustart.

## 0.2.53

- Reicht die LigaInsider-Startelfwahrscheinlichkeiten des Transfermarkts bis in Dashboard und Startelfplaner durch.
- Bewahrt vorhandene LI-Werte bei Fast-1T-Läufen, wenn der Schnellreport selbst keine neuen LigaInsider-Daten lädt.
- Speichert den aktualisierten Dashboard-Report nach Reportläufen dauerhaft, damit LI-Werte einen Add-on-Neustart überstehen.

## 0.2.52

- Zeigt die LI-Startelfwahrscheinlichkeit als farbcodierten Badge im Startelfplaner, in Kaderlisten, Marktchancen, Handlungsbedarf und Transfermarkt.
- Modernisiert das Trading Dashboard mit klarer Kartenhierarchie, responsivem 12-Spalten-Raster und einer kompakteren mobilen Darstellung.
- Hebt wichtige Aktionen, Statusinformationen und Kennzahlen deutlicher hervor.

## 0.2.51

- Färbt MW-Prognose und G/V auf den Spielerkacheln des Startelfplaners passend zur positiven oder negativen Tendenz ein.
- Zeigt in Kader-Wertentwicklung und Transfermarkt einen Tendenzpfeil für die 1T-Prognose im Vergleich zur letzten MW-Änderung.
- Ergänzt im Bereich Handlungsbedarf Ablaufdatum, Uhrzeit und die verbleibende Laufzeit in Stunden.

## 0.2.50

- Spieler lassen sich im Startelfplaner für die Startelf fixieren; mobil per langem Drücken. Formationswahl und „Beste Elf“ respektieren diese Fixierung.
- Zeigt G/V unter der MW-Prognose auf den Spielerkacheln und zusätzlich in der Auswahl für freie Startelfplätze.
- Rechtswisch hebt einen Halten-Status auf, Linkswisch einen Verkauf-Status; der Spieler ist danach jeweils neutral.
- Ergänzt einen eindeutigen Rücklink vom Startelfplaner zum Trading Dashboard.
- Aktualisiert den eigenen Cashwert der Managerbudgets beim Öffnen live aus der Kickbase-API und kennzeichnet Zeitbezug sowie Schätzwerte transparent.

## 0.2.49

- Markiert Formationen mit nichtnegativem Endbudget grün, mit negativem Endbudget gelb und nicht vollständig besetzbare Formationen rot.
- Hebt die aktive Formation zusätzlich mit einer Umrandung in ihrer jeweiligen Statusfarbe hervor.

## 0.2.48

- Ordnet die Managerbudget-Kacheln untereinander an und zeigt Cash, Kaderwert und Kaufkraft je Manager in getrennten Spalten.

## 0.2.47

- Behebt den Import des Manager-Audits, wenn GitHub Actions `latest.json` auf der Wurzelebene des Artefakts ablegt.

## 0.2.46

- Ein Klick auf einen freien Startelfplatz öffnet passende Kandidaten für genau diese Position.
- Für jeden Kandidaten wird das verbleibende Budget nach seiner Auswahl direkt angezeigt.

## 0.2.45

- Zeigt Namen, Cash, Kaderwert und Kaufkraft aller Manager als eigene Dashboard-Kachel.
- Synchronisiert den Manager-Audit des letzten Vollreports aus den geschützten GitHub-Actions-Artefakten.
- Kennzeichnet den eigenen API-Cashwert und die geschätzten Cashwerte der Mitmanager transparent.

## 0.2.44

- Der Startelfplaner ordnet die Spielerkacheln auf Desktop-Bildschirmen formationsgerecht auf einem Fußballfeld an; mobil bleibt die kompakte Liste erhalten.
- Bankspieler sind initial und nach dem Verschieben auf die Bank automatisch als Verkauf markiert. Beim Einsetzen in die Startelf wird die Markierung entfernt.

## 0.2.43

- Das Kaderwertdiagramm wird aus der vollständigen eigenen Transferhistorie rekonstruiert und am aktuellen, direkt von Kickbase gelieferten Kaderwert verankert.
- Historische Tage mit unvollständigen Marktwertdaten werden nicht mehr als zu niedrige Kaderwerte dargestellt.

## 0.2.42

- Transfermarkt und Handlungsbedarf lassen sich nun aufklappen und zeigen die letzten vier tatsächlichen täglichen Marktwertänderungen direkt aus der Kickbase-API.

## 0.2.41

- Die Prüfung nach „In Kickbase übernehmen“ versteht nun das aktuelle Kickbase-v4-Slotformat. Erfolgreich gespeicherte Aufstellungen werden nicht mehr fälschlich als Fehler gemeldet.

## 0.2.40

- Der mobile Startelfplaner lädt beim Öffnen die aktuelle Kickbase-Aufstellung und bietet nun „In Kickbase übernehmen“.
- Eine vollständige, positionsgerechte Elf aus dem echten Kader wird direkt über die Kickbase-API gespeichert.
- Simulierte Käufe werden vor der Übertragung erkannt und können nicht versehentlich in Kickbase gespeichert werden.

## 0.2.39

- „Beste 11“ bewertet innerhalb der zulässigen Budgetgrenze künftig Saison-Punkteschnitt, L3-Form, Startelfquote und ersten verfügbaren Gegner.
- Die 1T-Marktwertprognose wirkt nur als kleiner Tiebreaker und kann sportliche Punktedaten nicht überstimmen.
- Restbudget oberhalb der gewählten Grenze beeinflusst die Rangfolge nicht.

## 0.2.38

- Desktop-Ansicht des Startelfplaners erhält an Bankspielern sichtbare Schalter für „Verkauf“ und „Halten“.
- Die Restbudget-Kachel beobachtet die reale Kopfhöhe per ResizeObserver und bleibt beim Scrollen mit zusätzlichem Abstand vollständig unter dem Kopfbereich.

## 0.2.37

- „Beste 11“ ordnet die gefundene optimale Spielerkombination nun korrekt den Positionsplätzen der gewählten Formation zu.

## 0.2.36

- Die Kader-/Bankliste des mobilen Startelfplaners ist nach TW, ABW, MIT und ANG gruppiert.
- Dezente Positionsüberschriften und Trennlinien erleichtern das schnelle Scannen der Bank.

## 0.2.35

- Linkswisch markiert Spieler im mobilen Startelfplaner als unverkäuflich; ein weiterer Linkswisch entfernt die Halte-Markierung.
- Geschützte Spieler werden in „Beste 11“ und der Budgetrechnung nicht als Bankverkauf eingeplant.
- Geschützte Spieler erhalten eine grüne „HALTEN“-Kennzeichnung.

## 0.2.34

- Die Transfermarkt-Auswahl unter „Kauf simulieren“ ist nach Angebotsablauf sortiert; ablaufende Angebote stehen zuerst.

## 0.2.33

- Die feststehende Budget-Kachel im mobilen Startelfplaner berücksichtigt dynamisch die tatsächliche Höhe des Kopfbereichs.
- Restbudget und Budgetvorgabe bleiben dadurch beim Scrollen vollständig sichtbar.

## 0.2.32

- Im mobilen Startelfplaner lassen sich Transfermarktspieler mit frei eingetragenem Overpay als Kauf simulieren.
- Der Kaufpreis wird als Marktwert plus Overpay berechnet und fließt in Aufstellung, Bankverkäufe und Budgetgrenze ein.
- Simulierte Käufe können jederzeit einzeln entfernt werden.

## 0.2.31

- Der mobile Startelfplaner hat nun einen Schalter für die Budgetvorgabe: am Spieltag mindestens 0 EUR oder bis zu 5 Mio. EUR Defizit.
- „Beste 11“ optimiert seine Auswahl jeweils gegen die aktiv gewählte Budgetgrenze.

## 0.2.30

- „Beste 11“ berücksichtigt nun das Budget: Alle nicht aufgestellten Kaderspieler werden als Verkauf mit ihrem Marktwert gerechnet.
- Es werden nur punktstarke Kombinationen gewählt, die nach den geplanten Bankverkäufen mindestens -5 Mio. EUR Restbudget erreichen.
- Ist das selbst mit vollständigem Bankverkauf nicht möglich, zeigt der Planer einen klaren Hinweis statt eine irreführende Auswahl.

## 0.2.29

- Mobile Risikozeilen sind zweizeilig und überlagern Status und Betrag nicht mehr.
- Der Transfermarkt wird auf Smartphones als kompakte, mehrzeilige Kartenliste ohne horizontales Scrollen angezeigt.
- Rechtswisch funktioniert nun auch in der Startelf: Spieler werden auf die Bank verschoben und als Verkauf markiert.
- „Beste 11“ vergleicht alle gültigen Formationen und wählt die Kombination mit dem höchsten aktuellen Punkteschnitt.

## 0.2.28

- Mobiler Startelfplaner ergänzt: Startelf und Bank lassen sich per Drag-and-Drop oder Antippen planen.
- Rechtswisch auf einem Bankspieler markiert ihn als Verkauf; die Budget-Kachel zeigt Verkaufserlös, Restbudget und verbleibende Kadergröße.
- Die Kachel prüft sofort, ob nach Verkäufen noch eine gültige Kickbase-Formation möglich ist und nennt fehlende Positionen.

## 0.2.27

- Die Kaderwertgrafik beginnt nun am konfigurierten Ligastartdatum statt am frühesten verfügbaren Marktwert.
- `league_start_date` ist als Add-on-Einstellung verfügbar und wird auch von Voll- und Schnellreport verwendet.


## 0.2.26

- Die 1T-Kaderwert-Kachel zeigt die feste Kadergrenze `16` statt der Zahl verfügbarer Marktwertänderungen.
- Der Kaderzähler ist grün bei freiem Platz, gelb bei `16/16` und rot bei einer Überschreitung.


## 0.2.25

- Kaufkraft berücksichtigt nun auch eigene offene Gebote aus dem aktuellen Kickbase-Feld `uop` korrekt.
- Dadurch werden mehrere parallele Gebote, etwa auf Gruda, vollständig vom verfügbaren Maximalgebot abgezogen.


## 0.2.24

- Jede Kaderzeile zeigt nun direkt G/V seit dem eigenen Kauf, Kickbase-Gesamtpunkte und den aktuellen Kickbase-Punkteschnitt.
- Kaufpreise werden über die Liga-Transferhistorie geladen und pro Spieler zwischengespeichert; fehlende Kaufdaten werden nicht geschätzt.


## 0.2.23

- Das Dashboard kann „Vollreport“ und „Fast 1T“ direkt als GitHub-Action starten.
- Der dafür konfigurierte Fine-grained Token benötigt für `bastiwe/Kickbase-Kane` die Berechtigung `Actions: Read and write`; der fertige Snapshot wird danach weiterhin automatisch synchronisiert.


## 0.2.22

- Kacheln unter „Beste Chancen vor MW-Update“ sind nun aufklappbar und zeigen ebenfalls die vier letzten tatsächlichen Tagesänderungen eines Spielers.


## 0.2.21

- „Dein Kader · Wertentwicklung“ zeigt nun alle Kaderspieler statt nur fünf.
- Jede Zeile ist aufklappbar und lädt die vier letzten tatsächlichen täglichen Marktwertänderungen direkt aus der Kickbase-API.


## 0.2.20

- Kaderwertdiagramm nutzt nun die historische Marktwert-API von Kickbase statt einer vorausgesetzten lokalen SQLite-Historie.
- Der Verlauf berücksichtigt deinen verfügbaren Transferfeed; ohne zuordenbare ältere Transfers zeigt er transparent die historische Entwicklung des heutigen Kaders.


## 0.2.19

- Kaderwert-Kachel zeigt bei negativem Cash zusätzlich den bereinigten Gesamtwert: Kaderwert minus aktuellem Fehlbetrag.


## 0.2.18

- Live-Dashboard priorisiert Kickbase-Spielerprofile für Position, Status, Gesamtpunkte, Punkteschnitt, Minuten, Bilder, Vereins- und Marktwertdaten.
- Der GitHub-Snapshot bleibt auf die nicht von Kickbase gelieferten Werte beschränkt: Marktwertprognosen und LigaInsider-Signale.


## 0.2.17

- Dashboard zeigt unter dem verfügbaren Budget die Kaufkraft nach der Kickbase-33%-Regel, abzüglich eigener offener Gebote.
- Die erwartete Kaderentwicklung zeigt zusätzlich die tatsächlich erzielte Bilanz des letzten Marktwert-Updates aus der Kickbase-API.
- Die nicht handlungsrelevante Kennzahl „Trading-Chancen“ wurde entfernt.


## 0.2.16

- „Beste Chancen vor MW-Update“ zeigt ausschließlich Angebote mit Ablauf vor dem nächsten 22-Uhr-Update und mindestens +100.000 EUR erwarteter 1T-Steigerung.
- Die Kachel zeigt maximal sechs passende Spieler im 3×2-Raster.


## 0.2.15

- Lokale Schnellreport- und Vollreport-Buttons sowie die Fortschrittsanzeige aus dem Dashboard entfernt.
- Der Kopf zeigt stattdessen kompakt Quelle und Berliner Zeitpunkt des zuletzt geladenen Prognose-Snapshots.


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
