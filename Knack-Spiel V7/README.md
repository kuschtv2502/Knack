# Knack – spielbares Python-Kartenspiel

Diese Umsetzung basiert auf der mitgelieferten Datei `ORIGINAL-REGELWERK.txt`.
Sie enthält eine grafische Oberfläche, lokale Partien für 2–9 Spieler (ein
Mensch und 1–8 Computergegner), einen Direktmodus für zwei PCs im LAN oder
Internet, Nicknames, Karten- und Rundenanimationen, vollständige Runden- und
Münzverwaltung sowie einen Pot.

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

## Mit zwei PCs spielen

Beide PCs benötigen das entpackte Spiel. Jeder Spieler trägt auf der Startseite
seinen Nickname ein. Die Startmünzen werden vom Host festgelegt und automatisch
an den Gast übertragen.

### Im selben Netzwerk

1. Auf dem ersten PC **Partie eröffnen** wählen. Das Spiel zeigt dessen lokale
   IP-Adresse an, beispielsweise `192.168.178.25`.
2. Auf dem zweiten PC diese IP-Adresse in das Feld neben **Beitreten** eingeben
   und **Beitreten** anklicken.
3. Falls Windows beim Host-PC nachfragt, den Netzwerkzugriff für **private
   Netzwerke** erlauben.
4. Sobald die Verbindung steht, beginnt die Partie automatisch. Der Host
   beginnt die erste Runde; danach wechselt der Rundenstarter.

### Über das Internet

Beim Eröffnen zeigt das Spiel zusätzlich die öffentliche IPv4-Adresse an.
Damit ein zweiter PC über das Internet beitreten kann:

1. Im Router des Hosts TCP-Port `45454` an die angezeigte lokale IP-Adresse
   des Host-PCs weiterleiten.
2. Python bzw. das Spiel in der Windows-Firewall für die verwendete
   Netzwerkverbindung zulassen.
3. Der zweite Spieler gibt die öffentliche IPv4-Adresse oder einen darauf
   zeigenden Hostnamen ein und wählt **Beitreten**.

Die öffentliche IP wird beim Eröffnen über die einfache
[`api.ipify.org`](https://www.ipify.org/)–Schnittstelle ermittelt. Schlägt die
Abfrage fehl, kann sie auch über die Router-Oberfläche oder eine
„Wie lautet meine IP?“-Seite festgestellt werden.

Bei Anschlüssen mit CGNAT/DS-Lite kann der Router häufig keine eingehenden
IPv4-Verbindungen annehmen. Dann wird ein gemeinsames virtuelles Netzwerk wie
Tailscale/ZeroTier oder ein öffentlich betriebener Relay-Server benötigt; mit
der virtuellen IP funktioniert der bestehende Direktmodus ohne Änderungen.

Der Host verwaltet und prüft den Spielzustand. Die gegnerische Hand wird erst
nach dem Rundenende an den anderen PC übertragen. Die Direktverbindung
überträgt keine Passwörter, ist aber nicht TLS-verschlüsselt und sollte nur mit
bekannten Mitspielern verwendet werden.

Nach einem Rundenende kann ausschließlich der Host **Nächste Runde** wählen.
Beim Gast ist die Schaltfläche deaktiviert und zeigt an, dass auf den Host
gewartet wird. Auch direkt gesendete Gast-Anforderungen werden vom Host
abgelehnt.

## Bedienung

- Zu Beginn 2 bis 9 Spieler und 1 bis 99 Startmünzen wählen. Du bist immer
  Spieler 1. Im Direktspiel legt der Host die Startmünzen fest.
- Für den Einzeltausch eine eigene und eine mittlere Karte anklicken und dann
  **1 Karte tauschen** wählen.
- **Alle 3 tauschen** tauscht die komplette Hand mit der Mitte.
- **Schieben** setzt den Zug aus. Schieben alle Spieler nacheinander, wird die
  Mitte auf den sichtbaren Friedhof gelegt und neu ausgelegt. Der Friedhof
  zeigt seine oberste Karte und die Gesamtzahl der abgelegten Karten.
- **Zumachen** gibt jedem anderen Spieler noch genau einen Zug und beendet
  danach die Runde.
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

Die Oberfläche animiert Kartenauswahl, Einzel- und Dreiertausch, eine neue
Mitte nach gemeinsamem Schieben einschließlich des Wegs zum Friedhof, das
Aufdecken gegnerischer Hände, verlorene Münzen, Rundensieger sowie Knack und
Jackpot. Während einer Animation sind weitere Eingaben
gesperrt, damit lokale und Netzwerkpartien synchron bleiben. Im Menü
**Spiel → Animationen** können sämtliche Effekte jederzeit deaktiviert werden.

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

Die Tests prüfen unter anderem Kartenverteilung, Farbauswertung, Halben,
AAA, verbotene 31, Gleichstände, Schieben, Tauschen, Zumachen, die Zuggrenze
für Knack, Jackpot, Netzwerksynchronisierung und Pot-Auszahlung.

## Dateien

- `main.py` – Startpunkt
- `BUILD_KNACK_EXE.bat` – erstellt eine weitergebbare `Knack.exe`
- `knack/engine.py` – Regel- und Spiellogik
- `knack/ui.py` – grafische Tkinter-Oberfläche und Computergegner
- `knack/network.py` – LAN-Verbindung, Zustandsfilterung und Synchronisierung
- `tests/test_engine.py` – automatisierte Regeltests
- `tests/test_network.py` – Netzwerk- und Synchronisierungstests
- `ORIGINAL-REGELWERK.txt` – unveränderte Regelvorlage

