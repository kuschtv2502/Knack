# Knack – spielbares Python-Kartenspiel

Diese Umsetzung basiert auf der mitgelieferten Datei `ORIGINAL-REGELWERK.txt`.
Sie enthält eine grafische Oberfläche, lokale Partien für 2–4 Spieler (ein
Mensch und 1–3 Computergegner), einen Direktmodus für zwei PCs im LAN oder
Internet, Nicknames, vollständige Runden- und Münzverwaltung sowie einen Pot.

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

## Mit zwei PCs spielen

Beide PCs benötigen das entpackte Spiel. Jeder Spieler trägt auf der Startseite
seinen Nickname ein.

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

- Zu Beginn 2, 3 oder 4 Spieler wählen. Du bist immer Spieler 1.
- Für den Einzeltausch eine eigene und eine mittlere Karte anklicken und dann
  **1 Karte tauschen** wählen.
- **Alle 3 tauschen** tauscht die komplette Hand mit der Mitte.
- **Schieben** setzt den Zug aus. Schieben alle Spieler nacheinander, wird die
  Mitte auf den Friedhof gelegt und neu ausgelegt.
- **Zumachen** gibt jedem anderen Spieler noch genau einen Zug und beendet
  danach die Runde.
- **KNACK!** und **JACKPOT!** werden nur aktiviert, wenn die jeweilige
  Bedingung erfüllt ist.
- Nach Rundenende werden alle Hände und Wertungen offengelegt. Mit
  **Nächste Runde** geht es weiter.

## Umgesetzte Regelauslegung

Das Original lässt einige Details offen. Damit jede Spielsituation eindeutig
abläuft, gelten diese sichtbar im Hilfe-Menü dokumentierten Annahmen:

1. Erlaubt sind der Tausch genau einer Handkarte gegen genau eine Mittelkarte
   sowie der komplette Dreiertausch.
2. Bei Knack oder Jackpot wird unter den übrigen Spielern die schwächste Hand
   ermittelt; sie verliert eine Münze. Bei vollständigem Gleichstand verlieren
   alle gleich schwachen Spieler. Beim Jackpot wird anschließend der gesamte
   Pot – einschließlich der gerade gezahlten Münze(n) – ausgezahlt.
3. „Ass, Ass, X“ bedeutet genau zwei Asse und eine Nicht-Ass-Karte. AAA bleibt
   dadurch immer der eigene Sonderfall aus dem Original.
4. Bei einer Halben dient die höchste in der Hand vorhandene Farbe als
   Farb-Tiebreaker.
5. Wenn der Nachziehstapel keine drei Karten mehr enthält, wird der Friedhof
   gemischt und als neuer Nachziehstapel verwendet.
6. Sollten alle letzten Spieler durch einen vollständigen Gleichstand zugleich
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
AAA, verbotene 31, Gleichstände, Schieben, Tauschen, Zumachen, Knack,
Jackpot und Pot-Auszahlung.

## Dateien

- `main.py` – Startpunkt
- `knack/engine.py` – Regel- und Spiellogik
- `knack/ui.py` – grafische Tkinter-Oberfläche und Computergegner
- `knack/network.py` – LAN-Verbindung, Zustandsfilterung und Synchronisierung
- `tests/test_engine.py` – automatisierte Regeltests
- `tests/test_network.py` – Netzwerk- und Synchronisierungstests
- `ORIGINAL-REGELWERK.txt` – unveränderte Regelvorlage

