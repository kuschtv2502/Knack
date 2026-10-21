# Knack – spielbares Python-Kartenspiel

Diese Umsetzung basiert auf der mitgelieferten Datei `ORIGINAL-REGELWERK.txt`.
Sie enthält eine grafische Oberfläche, lokale Partien für 2–9 Spieler (ein
Mensch und 1–8 Computergegner) sowie einen zentralen Online-Lobby-Browser für
Zwei-Spieler-Partien. Hinzu kommen
Nicknames, Karten- und Rundenanimationen, vollständige Runden- und
Münzverwaltung, ein Pot, dezente Spieltöne sowie echte Kartenbilder aus der
mitgelieferten Bildvorlage. Menü, Lobby und Spieltisch verwenden das elegante
dunkelgrün-goldene Design der drei bereitgestellten Gestaltungsvorlagen.

## Start unter Windows

1. Den Ordner `Knack-Spiel` entpacken bzw. öffnen.
2. Falls noch nicht vorhanden: Python 3.10 oder neuer von
   <https://www.python.org/downloads/> installieren. Bei der Installation
   „Add Python to PATH“ aktivieren.
3. `START_KNACK.bat` doppelt anklicken.

Alternativ in einer Eingabeaufforderung im Spielordner:

```text
py -3 main.py
```

Es werden keine externen Python-Pakete benötigt. Tkinter gehört zur normalen
Python-Installation unter Windows.

## Eine weitergebbare Windows-EXE erstellen

1. `BUILD_KNACK_EXE.bat` doppelt anklicken.
2. Beim ersten Durchlauf wird in einer isolierten Build-Umgebung PyInstaller
   installiert; dafür ist einmalig eine Internetverbindung erforderlich.
3. Vor dem Bau werden automatisch alle Spieltests ausgeführt.
4. Nach erfolgreichem Abschluss liegt die fertige Datei unter
   `dist\Knack.exe`.

Die erzeugte `Knack.exe` kann einzeln an andere Windows-PCs weitergegeben
werden. Dort wird weder Python noch ein zusätzliches Paket benötigt. Da die
EXE nicht digital signiert ist, kann Windows beim ersten Start eine
SmartScreen-Warnung anzeigen. Für Netzwerkspiele muss die Firewall die EXE
gegebenenfalls zulassen.

## Online-Lobbys über einen zentralen Testserver

Mit dem neuen Lobby-Modus müssen die einzelnen Spieler weder ihre IP-Adresse
weitergeben noch einen Port an ihrem Router öffnen. Nur der PC, auf dem der
zentrale Lobby-Server läuft, muss einmalig erreichbar eingerichtet werden.

### Deinen PC als Lobby-Server starten

1. Auf deinem PC `START_LOBBY_SERVER.bat` doppelt anklicken und das geöffnete
   Fenster während des Testbetriebs offen lassen.
2. In der Windows-Firewall den Netzwerkzugriff für Python erlauben, falls
   Windows danach fragt.
3. Im Router TCP-Port `45455` an diesen PC weiterleiten. Diese Freigabe ist
   ausschließlich auf dem zentralen Server-PC notwendig.
4. `kuschtv.zapto.org` muss auf die öffentliche Adresse dieses Routers zeigen.
   Diese Serveradresse ist fest im Spiel hinterlegt und muss von den
   Mitspielern nicht eingegeben werden.

### Lobby erstellen oder beitreten

1. Nickname und gewünschte Startmünzen eintragen.
2. **Lobby-Browser öffnen** wählen. Das Spiel verbindet sich automatisch mit
   `kuschtv.zapto.org:45455`.
3. Einen Lobbyname eingeben und **Lobby erstellen** wählen – oder eine freie
   Lobby markieren und **Beitreten** anklicken.
4. Sobald ein Gast beitritt, startet die Partie automatisch. Der Ersteller
   bleibt Spiel-Host und darf nach Rundenende die nächste Runde starten.

Der Server kann gleichzeitig mehrere voneinander getrennte Lobbys vermitteln.
Er kennt die Spielregeln und Karten nicht, sondern leitet die bereits
gefilterten Spielnachrichten nur zwischen den beiden Teilnehmern weiter. Die
gegnerische Hand bleibt bis zum Rundenende verborgen.

Der aktuelle Testserver verwendet bewusst nur Python-Bordmittel und eine
einfache unverschlüsselte TCP-Verbindung. Er ist für private Tests mit bekannten
Mitspielern gedacht. Für einen dauerhaft öffentlichen Betrieb sollte später
TLS, Zugriffsschutz, Protokollierung und eine Begrenzung missbräuchlicher
Anfragen ergänzt werden.

## Bedienung

- Zu Beginn 2 bis 9 Spieler und 1 bis 99 Startmünzen wählen. Du bist immer
  Spieler 1. Im Onlinespiel legt der Lobby-Ersteller die Startmünzen fest.
- Für den Einzeltausch eine eigene und eine mittlere Karte anklicken und dann
  **1 Karte tauschen** wählen.
- **Alle 3 tauschen** tauscht die komplette Hand mit der Mitte.
- **Schieben** setzt den Zug aus. Schieben alle Spieler nacheinander, wird die
  Mitte auf den sichtbaren Friedhof gelegt und neu ausgelegt. Der Friedhof
  zeigt seine oberste Karte und die Gesamtzahl der abgelegten Karten.
- **Zumachen** gibt jedem anderen Spieler noch genau einen Zug. Der Auslöser
  wird mit einem rot pulsierenden Rahmen und „ZUGEMACHT“ markiert.
- Bei den folgenden Spielern heißt der Button **Mit zumachen**. Wer ihn nutzt,
  wird ebenfalls rot markiert und beendet damit seinen letzten Zug. Die
  Schlussrunde wird dadurch nicht verlängert oder neu gestartet.
- **KNACK!** und **JACKPOT!** werden nur aktiviert, wenn die jeweilige
  Bedingung erfüllt ist.
- Für **KNACK** müssen ein Ass und eine 10-Punkte-Karte derselben Farbe auf
  deiner Hand liegen; eine weitere 10-Punkte-Karte dieser Farbe muss in der
  Mitte liegen. Die dritte Handkarte wird nicht mitgezählt. Das Ass muss
  zwingend auf deiner Hand liegen.
- Ein Tausch beendet deinen Zug. Entsteht die passende KNACK-Kombination erst
  dadurch, darf sie nicht noch im selben Zug gerufen werden.
- Beim **JACKPOT** verliert niemand eine Münze. Der Gewinner erhält nur den
  bereits vorhandenen Pot.
- Nach Rundenende werden alle Hände und Wertungen offengelegt. Mit
  **Nächste Runde** geht es weiter. Alle Rundensieger werden goldfarben
  hervorgehoben und ausdrücklich genannt.

## Animationen

Die Oberfläche animiert nun auch das Austeilen zu Rundenbeginn, den Wechsel
des aktiven Spielers, das rote Aufleuchten beim Zu- und Mit-Zumachen und das
Werfen der drei Gewinnerkarten bei Knack oder Jackpot. Zusätzlich bleiben
Kartenauswahl, Einzel- und Dreiertausch, eine neue
Mitte nach gemeinsamem Schieben einschließlich des Wegs zum Friedhof, das
Aufdecken gegnerischer Hände, verlorene Münzen und Rundensieger animiert.
Während einer Animation sind weitere Eingaben
gesperrt, damit lokale und Netzwerkpartien synchron bleiben. Im Menü
**Spiel → Animationen** können sämtliche Effekte jederzeit deaktiviert werden.

## Gestaltung

Alle drei Hauptansichten wurden an die elegante Designvorlage angepasst:

- durchgängiger dunkelgrüner Filz-Spieltisch mit dezenten Kartenmotiven,
- feine goldene Rahmen und Pik-Ornamente,
- große goldene Serifentitel,
- dunkle Eingabefelder und goldene Hauptaktionen,
- größere Hand-, Mittel- und Gegnerkarten,
- neu gestaltete Lobbyliste, Rundenprotokoll und Kurzmerker.

Der Hintergrund liegt als fertige PNG-Datei bei. Das Spiel benötigt für die
Darstellung weiterhin keine externen Python-Pakete.

## Töne

Kartenwahl und -bewegung, Austeilen, Zugwechsel, Münzen, Rundensieg, Knack und
Jackpot besitzen kurze WAV-Effekte. Sie werden lokal abgespielt und benötigen
keine Zusatzpakete oder Internetverbindung. Über **Spiel → Töne** lassen sich
alle Geräusche jederzeit gemeinsam ein- oder ausschalten.

## Kartenbilder

Alle 32 im Spiel verwendeten Karten (7 bis Ass in vier Farben) wurden einzeln
und ohne Überschrift, Joker oder Nachbarkarten aus der bereitgestellten
Vorlage ausgeschnitten. Hand und Mitte verwenden große Bilder; Gegner und
Friedhof passend verkleinerte Varianten. Die drei Mittelkarten stehen exakt
über den drei eigenen Handkarten; der separat rechts platzierte Friedhof
verschiebt diese Achse nicht mehr. Gegnerkarten sind auch bei neun Spielern
gut erkennbar, während die Oberfläche bei Bedarf nur die Abstände verdichtet.
Die Rückseite wurde passend zur grünen und goldenen Spieloberfläche gestaltet.

Die fertigen PNG-Dateien benötigen kein Zusatzpaket. Nur zum erneuten
Erzeugen aus der ursprünglichen JPG-Vorlage wird Pillow benötigt; dafür liegt
`tools/generate_card_assets.py` bei.

## Umgesetzte Regelauslegung

Das Original lässt einige Details offen. Damit jede Spielsituation eindeutig
abläuft, gelten diese sichtbar im Hilfe-Menü dokumentierten Annahmen:

1. Erlaubt sind der Tausch genau einer Handkarte gegen genau eine Mittelkarte
   sowie der komplette Dreiertausch.
2. Jeder Tausch beendet den Zug. Ein erst durch den eigenen Tausch entstandener
   Knack darf daher nicht sofort im selben Zug gerufen werden.
3. Für einen Knack werden nur Ass + 10-Punkte-Karte gleicher Farbe auf der
   Hand sowie eine weitere passende 10-Punkte-Karte in der Mitte verwendet.
   Die dritte Handkarte bleibt unberücksichtigt – auch wenn sie dieselbe Farbe
   hat. Das Ass in der Mitte genügt nicht; es muss auf der Hand liegen.
4. Bei Knack wird unter den übrigen Spielern die schwächste Hand ermittelt;
   sie verliert eine Münze. Bei vollständigem Gleichstand verlieren alle
   gleich schwachen Spieler.
5. Beim Jackpot verliert niemand eine Münze. Der Rufer erhält den bereits vor
   dem Jackpot vorhandenen Pot.
6. „Ass, Ass, X“ bedeutet genau zwei Asse und eine Nicht-Ass-Karte. AAA bleibt
   dadurch immer der eigene Sonderfall aus dem Original.
7. Bei einer Halben dient die höchste in der Hand vorhandene Farbe als
   Farb-Tiebreaker.
8. Wenn der Nachziehstapel keine drei Karten mehr enthält, wird der Friedhof
   gemischt und als neuer Nachziehstapel verwendet.
9. Sollten alle letzten Spieler durch einen vollständigen Gleichstand zugleich
   ihre letzte Münze verlieren, endet die Partie unentschieden.
10. Nach dem ersten Zumachen dürfen die folgenden Spieler ebenfalls mit
    zumachen. Dies verbraucht den jeweiligen letzten Zug, setzt die Anzahl der
    verbleibenden Schlussrundenzüge aber nicht zurück.

Die ausdrücklich formulierte Rangfolge wurde direkt umgesetzt:

`Halbe > normale Hand > AAA > verbotene 31`

AAA verliert, zahlt aber keine Münze. Eine gleichfarbige 31 ist die
schlechteste Hand. Bei normalen Händen zählt nur die beste Farbe; bei
Punktgleichheit gilt `Karo < Herz < Pik < Kreuz`.

## Tests ausführen

Im Spielordner:

```text
py -3 -m unittest discover -s tests -v
```

Die 37 Tests prüfen unter anderem Kartenverteilung, Farbauswertung, Halben,
AAA, verbotene 31, Gleichstände, Schieben, Tauschen, Zumachen und Mit-Zumachen,
die Zuggrenze für Knack, Jackpot, Netzwerksynchronisierung, Lobby-Erstellung,
Lobby-Beitritt, Relay-Nachrichten und Pot-Auszahlung.

## Dateien

- `main.py` – Startpunkt
- `lobby_server.py` – Startpunkt des zentralen Lobby-/Relay-Servers
- `START_LOBBY_SERVER.bat` – startet den Lobby-Server unter Windows
- `BUILD_KNACK_EXE.bat` – erstellt eine weitergebbare `Knack.exe`
- `knack/engine.py` – Regel- und Spiellogik
- `knack/ui.py` – grafische Tkinter-Oberfläche und Computergegner
- `knack/network.py` – Zustandsfilterung und Synchronisierung
- `knack/lobby.py` – Lobby-Browser-Protokoll und zentraler Relay-Server
- `assets/cards/large/*.png` – große Kartenbilder für Hand und Mitte
- `assets/cards/small/*.png` – kleine Kartenbilder für Gegner und Friedhof
- `assets/background/table.png` – grüner Spieltisch-Hintergrund
- `assets/sounds/*.wav` – lokale Spieltöne
- `tools/generate_card_assets.py` – erzeugt Kartenbilder aus der JPG-Vorlage
- `tools/generate_sounds.py` – reproduziert die mitgelieferten WAV-Dateien
- `tests/test_engine.py` – automatisierte Regeltests
- `tests/test_network.py` – Netzwerk- und Synchronisierungstests
- `ORIGINAL-REGELWERK.txt` – unveränderte Regelvorlage

