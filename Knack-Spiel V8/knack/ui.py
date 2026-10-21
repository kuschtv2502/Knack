"""Tkinter-Oberfläche für Knack."""

from __future__ import annotations

import os
import queue
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

try:
    import winsound
except ImportError:  # pragma: no cover - nur für Starts außerhalb von Windows
    winsound = None  # type: ignore[assignment]

from .engine import (
    Card,
    DEFAULT_STARTING_COINS,
    IllegalMove,
    KnackGame,
    MAX_PLAYERS,
    MAX_STARTING_COINS,
    MIN_PLAYERS,
    MIN_STARTING_COINS,
    SUIT_SYMBOLS,
    best_exchange,
    evaluate_hand,
)
from .network import (
    DEFAULT_PORT,
    LanClient,
    LanHost,
    game_from_snapshot,
    game_snapshot,
    local_ip_address,
)


BG = "#102a24"
PANEL = "#173b33"
PANEL_2 = "#1f4a40"
CREAM = "#f8f4e8"
INK = "#17201d"
GOLD = "#e2b84b"
MUTED = "#b8c9c2"
RED = "#c53f4a"
GREEN = "#2f8f64"
WINNER_BG = "#66531f"


ASSUMPTIONS = """Auslegung der im Original offenen Regelstellen

• Tauschen: Erlaubt sind entweder genau eine Handkarte gegen genau eine
  Mittelkarte oder alle drei Handkarten gegen alle drei Mittelkarten.
• Ein Tausch beendet den Zug. Ein erst durch den eigenen Tausch entstandener
  KNACK darf daher nicht sofort im selben Zug gerufen werden.
• KNACK verwendet gezielt Ass + 10-Punkte-Karte derselben Farbe von der Hand
  und eine weitere passende 10-Punkte-Karte aus der Mitte. Die dritte
  Handkarte wird nicht mitgezählt; das Ass muss zwingend auf der Hand liegen.
• Bei KNACK wird unter den übrigen Spielern die schwächste Hand ermittelt;
  diese verliert eine Münze. Gleichstände teilen die Niederlage.
• Beim JACKPOT verliert niemand eine Münze. Der Gewinner erhält ausschließlich
  den bereits vorhandenen Pot.
• „Ass, Ass, X“ bedeutet genau zwei Asse und eine Nicht-Ass-Karte.
• Bei einer Halben ist die höchste enthaltene Farbe der Farb-Tiebreaker.
• Reicht der Nachziehstapel nicht, wird der Friedhof neu gemischt.
• Verlieren alle letzten Spieler gleichzeitig ihre letzte Münze, endet die
  Partie ausnahmsweise unentschieden.

Diese Annahmen ändern keine ausdrücklich formulierte Regel; sie schließen nur
Lücken, damit das Spiel vollständig und reproduzierbar spielbar ist."""


class KnackApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Knack – Kartenspiel")
        self.root.geometry("1100x820")
        self.root.minsize(920, 700)
        self.root.configure(bg=BG)
        self.game: Optional[KnackGame] = None
        self.selected_hand: Optional[int] = None
        self.selected_center: Optional[int] = None
        self.message = ""
        self.ai_job: Optional[str] = None
        self.screen: Optional[tk.Frame] = None
        self.game_ui_ready = False
        self.local_player_id = 0
        self.network_role: Optional[str] = None
        self.network_host: Optional[LanHost] = None
        self.network_client: Optional[LanClient] = None
        self.network_poll_job: Optional[str] = None
        self.awaiting_network = False
        self.nickname = "Spieler"
        self.starting_coins = DEFAULT_STARTING_COINS
        self.pending_remote_nickname = "Gast"
        self.host_local_address = ""
        self.host_public_address = "wird ermittelt …"
        self.animations_enabled = tk.BooleanVar(value=True)
        self.sounds_enabled = tk.BooleanVar(value=True)
        self.animation_running = False
        self.animation_jobs: list[str] = []
        self.animation_overlays: list[tk.Widget] = []
        self.visual_snapshot: Optional[dict] = None
        self._configure_style()
        self._build_menu()
        self.show_start_screen()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Accent.TButton",
            font=("Segoe UI", 11, "bold"),
            foreground=INK,
            background=GOLD,
            padding=(15, 9),
        )
        style.map("Accent.TButton", background=[("active", "#f1cb65")])
        style.configure(
            "Game.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground=CREAM,
            background=GREEN,
            padding=(11, 8),
        )
        style.map(
            "Game.TButton",
            background=[("active", "#3ba879"), ("disabled", "#31564a")],
            foreground=[("disabled", "#87a197")],
        )
        style.configure(
            "Danger.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground=CREAM,
            background="#9f3542",
            padding=(11, 8),
        )

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        game_menu = tk.Menu(menu, tearoff=False)
        game_menu.add_command(label="Neues Spiel", command=self.show_start_screen)
        game_menu.add_checkbutton(
            label="Animationen",
            variable=self.animations_enabled,
            command=self._toggle_animations,
        )
        game_menu.add_checkbutton(
            label="Töne",
            variable=self.sounds_enabled,
            command=self._toggle_sounds,
        )
        game_menu.add_separator()
        game_menu.add_command(label="Beenden", command=self.root.destroy)
        menu.add_cascade(label="Spiel", menu=game_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Regelauslegung", command=self.show_assumptions)
        help_menu.add_command(label="Kurzregeln", command=self.show_rules)
        menu.add_cascade(label="Hilfe", menu=help_menu)
        self.root.config(menu=menu)

    def _clear(self) -> None:
        self._cancel_animations(restore=False)
        if self.ai_job is not None:
            try:
                self.root.after_cancel(self.ai_job)
            except tk.TclError:
                pass
            self.ai_job = None
        if self.screen is not None:
            self.screen.destroy()
            self.screen = None
        self.game_ui_ready = False
        self.visual_snapshot = None

    def show_start_screen(self) -> None:
        self._stop_network()
        self._clear()
        self.game = None
        self.local_player_id = 0
        outer = tk.Frame(self.root, bg=BG)
        outer.place(x=0, y=0, relwidth=1, relheight=1)
        self.screen = outer
        card = tk.Frame(outer, bg=PANEL, padx=50, pady=42)
        card.place(relx=0.5, rely=0.48, anchor="center")

        tk.Label(
            card,
            text="KNACK",
            font=("Segoe UI", 35, "bold"),
            fg=GOLD,
            bg=PANEL,
        ).pack()
        tk.Label(
            card,
            text="Das Kartenspiel nach euren Hausregeln",
            font=("Segoe UI", 14),
            fg=CREAM,
            bg=PANEL,
        ).pack(pady=(0, 28))
        tk.Label(
            card,
            text=(
                "Tausche clever, mache rechtzeitig zu – und hüte dich vor der\n"
                "verbotenen 31. Du spielst gegen Computergegner."
            ),
            justify="center",
            font=("Segoe UI", 11),
            fg=MUTED,
            bg=PANEL,
        ).pack(pady=(0, 16))

        nickname_row = tk.Frame(card, bg=PANEL)
        nickname_row.pack(pady=(0, 12))
        tk.Label(
            nickname_row,
            text="Nickname:",
            font=("Segoe UI", 11, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).pack(side="left", padx=(0, 10))
        self.nickname_var = tk.StringVar(value=self.nickname)
        tk.Entry(
            nickname_row,
            textvariable=self.nickname_var,
            width=18,
            font=("Segoe UI", 10),
        ).pack(side="left", ipady=4)

        picker = tk.Frame(card, bg=PANEL)
        picker.pack(pady=(0, 25))
        tk.Label(
            picker,
            text="Spielerzahl:",
            font=("Segoe UI", 12, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).pack(side="left", padx=(0, 12))
        player_count = tk.IntVar(value=3)
        combo = ttk.Combobox(
            picker,
            state="readonly",
            values=tuple(range(MIN_PLAYERS, MAX_PLAYERS + 1)),
            textvariable=player_count,
            width=5,
            font=("Segoe UI", 11),
        )
        combo.pack(side="left")
        tk.Label(
            picker,
            text="Startmünzen:",
            font=("Segoe UI", 12, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).pack(side="left", padx=(24, 12))
        self.starting_coins_var = tk.StringVar(value=str(self.starting_coins))
        tk.Spinbox(
            picker,
            from_=MIN_STARTING_COINS,
            to=MAX_STARTING_COINS,
            textvariable=self.starting_coins_var,
            width=5,
            justify="center",
            font=("Segoe UI", 11),
        ).pack(side="left", ipady=3)

        ttk.Button(
            card,
            text="Lokales Spiel starten",
            style="Accent.TButton",
            command=lambda: self.start_game(player_count.get()),
        ).pack(pady=(0, 15))

        separator = tk.Frame(card, bg="#3d6258", height=1, width=440)
        separator.pack(fill="x", pady=(5, 14))
        tk.Label(
            card,
            text="DIREKTSPIEL · LAN ODER INTERNET",
            font=("Segoe UI", 11, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).pack()
        tk.Label(
            card,
            text="IP-Adresse oder Hostname des eröffnenden PCs verwenden.",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=PANEL,
        ).pack(pady=(2, 8))
        lan_row = tk.Frame(card, bg=PANEL)
        lan_row.pack(pady=(0, 12))
        ttk.Button(
            lan_row,
            text="Partie eröffnen",
            style="Game.TButton",
            command=self._host_lan_game,
        ).pack(side="left", padx=(0, 8))
        self.join_ip_var = tk.StringVar()
        tk.Entry(
            lan_row,
            textvariable=self.join_ip_var,
            width=16,
            font=("Segoe UI", 10),
        ).pack(side="left", ipady=5, padx=(0, 6))
        ttk.Button(
            lan_row,
            text="Beitreten",
            style="Game.TButton",
            command=self._join_lan_game,
        ).pack(side="left")
        tk.Button(
            card,
            text="Regelauslegung ansehen",
            command=self.show_assumptions,
            relief="flat",
            bg=PANEL,
            fg=MUTED,
            activebackground=PANEL,
            activeforeground=CREAM,
            cursor="hand2",
            font=("Segoe UI", 10, "underline"),
        ).pack()

    def start_game(self, player_count: int) -> None:
        nickname = self._validated_nickname()
        if nickname is None:
            return
        starting_coins = self._validated_starting_coins()
        if starting_coins is None:
            return
        self._stop_network()
        self.network_role = None
        self.local_player_id = 0
        self.game = KnackGame(player_count, starting_coins=starting_coins)
        self.game.players[0].name = nickname
        self.selected_hand = None
        self.selected_center = None
        self.message = "Wähle eine Aktion. Für den Einzeltausch je eine Karte anklicken."
        self.refresh()
        self._schedule_ai_if_needed()

    def _host_lan_game(self) -> None:
        nickname = self._validated_nickname()
        if nickname is None:
            return
        starting_coins = self._validated_starting_coins()
        if starting_coins is None:
            return
        self._stop_network()
        try:
            host = LanHost(DEFAULT_PORT)
            host.start()
        except OSError as exc:
            messagebox.showerror(
                "Direktpartie nicht möglich",
                f"Der Netzwerk-Port {DEFAULT_PORT} konnte nicht geöffnet werden.\n\n{exc}",
                parent=self.root,
            )
            return
        self.network_role = "host"
        self.network_host = host
        self.local_player_id = 0
        self.pending_remote_nickname = "Gast"
        self.starting_coins = starting_coins
        self.host_local_address = local_ip_address()
        self.host_public_address = "wird ermittelt …"
        self._show_network_waiting(
            "Partie ist geöffnet",
            self._host_waiting_text(),
        )
        host.discover_public_ip()
        self._schedule_network_poll()

    def _join_lan_game(self) -> None:
        nickname = self._validated_nickname()
        if nickname is None:
            return
        address = self.join_ip_var.get().strip()
        if not address:
            messagebox.showinfo(
                "IP-Adresse fehlt",
                "Bitte die IP-Adresse oder den Hostnamen des Host-PCs eingeben.",
                parent=self.root,
            )
            return
        self._stop_network()
        client = LanClient()
        self.network_role = "client"
        self.network_client = client
        self.local_player_id = 1
        client.connect(address, DEFAULT_PORT)
        self._show_network_waiting(
            "Verbindung wird hergestellt",
            f"Verbinde mit {address}:{DEFAULT_PORT} …",
        )
        self._schedule_network_poll()

    def _validated_nickname(self) -> Optional[str]:
        raw = self.nickname_var.get().strip()
        nickname = "".join(character for character in raw if character.isprintable())[:20]
        if not nickname:
            messagebox.showinfo(
                "Nickname fehlt",
                "Bitte einen Nickname mit maximal 20 Zeichen eingeben.",
                parent=self.root,
            )
            return None
        self.nickname = nickname
        return nickname

    def _validated_starting_coins(self) -> Optional[int]:
        try:
            value = int(self.starting_coins_var.get().strip())
        except (AttributeError, ValueError):
            value = 0
        if not MIN_STARTING_COINS <= value <= MAX_STARTING_COINS:
            messagebox.showinfo(
                "Ungültige Startmünzen",
                f"Bitte einen Wert zwischen {MIN_STARTING_COINS} und "
                f"{MAX_STARTING_COINS} eingeben.",
                parent=self.root,
            )
            return None
        self.starting_coins = value
        return value

    def _host_waiting_text(self) -> str:
        return (
            "Adresse für dasselbe Netzwerk:\n"
            f"{self.host_local_address}\n\n"
            "Adresse für das Internet:\n"
            f"{self.host_public_address}\n\n"
            f"TCP-Port: {DEFAULT_PORT}\n"
            "Für Internetspiele muss dieser Port im Router an den Host-PC "
            "weitergeleitet sein.\n\nWarte auf Mitspieler …"
        )

    def _show_network_waiting(self, title: str, detail: str) -> None:
        self._clear()
        outer = tk.Frame(self.root, bg=BG)
        outer.place(x=0, y=0, relwidth=1, relheight=1)
        self.screen = outer
        card = tk.Frame(outer, bg=PANEL, padx=55, pady=45)
        card.place(relx=0.5, rely=0.48, anchor="center")
        tk.Label(
            card,
            text=title,
            font=("Segoe UI", 24, "bold"),
            fg=GOLD,
            bg=PANEL,
        ).pack()
        self.wait_detail_label = tk.Label(
            card,
            text=detail,
            justify="center",
            font=("Segoe UI", 12),
            fg=CREAM,
            bg=PANEL,
        )
        self.wait_detail_label.pack(pady=(18, 24))
        ttk.Button(
            card,
            text="Abbrechen",
            style="Game.TButton",
            command=self.show_start_screen,
        ).pack()

    def _schedule_network_poll(self) -> None:
        if self.network_poll_job is None and self.network_role is not None:
            self.network_poll_job = self.root.after(75, self._poll_network_events)

    def _poll_network_events(self) -> None:
        self.network_poll_job = None
        endpoint = self.network_host if self.network_role == "host" else self.network_client
        if endpoint is None:
            return
        while True:
            try:
                event = endpoint.events.get_nowait()
            except queue.Empty:
                break
            if not self._handle_network_event(event):
                return
        self._schedule_network_poll()

    def _handle_network_event(self, event: dict) -> bool:
        event_type = event.get("event")
        if event_type == "public_ip":
            self.host_public_address = str(event.get("address", "nicht verfügbar"))
            if self.network_role == "host" and self.game is None:
                self.wait_detail_label.configure(text=self._host_waiting_text())
            return True
        if event_type == "public_ip_failed":
            self.host_public_address = "nicht verfügbar (manuell ermitteln)"
            if self.network_role == "host" and self.game is None:
                self.wait_detail_label.configure(text=self._host_waiting_text())
            return True
        if event_type == "connected":
            if self.network_role == "host":
                self.wait_detail_label.configure(
                    text="Mitspieler verbunden. Nickname wird empfangen …"
                )
            elif self.network_client is not None:
                try:
                    self.network_client.send(
                        {"type": "hello", "nickname": self.nickname}
                    )
                except ConnectionError as exc:
                    self.message = str(exc)
            return True
        if event_type == "connect_failed":
            messagebox.showerror(
                "Verbindung fehlgeschlagen",
                "Der Host-PC konnte nicht erreicht werden. Prüfe IP-Adresse oder "
                "Hostname, Windows-Firewall und bei Internetspielen die "
                f"Portweiterleitung für TCP {DEFAULT_PORT}.\n\n{event.get('message', '')}",
                parent=self.root,
            )
            self.show_start_screen()
            return False
        if event_type == "message":
            message = event.get("message", {})
            if self.network_role == "host":
                if message.get("type") == "hello" and self.game is None:
                    self._start_network_game(str(message.get("nickname", "Gast")))
                else:
                    self._handle_remote_action(message)
            elif message.get("type") == "state":
                action_was_pending = self.awaiting_network
                self.game = game_from_snapshot(message)
                self.local_player_id = int(message["viewer_id"])
                self.awaiting_network = False
                if action_was_pending:
                    self.selected_hand = None
                    self.selected_center = None
                self.message = ""
                self.refresh()
            elif message.get("type") == "error":
                self.awaiting_network = False
                self.message = str(message.get("message", "Aktion abgelehnt."))
                self.refresh()
            return True
        if event_type in ("disconnected", "error"):
            detail = event.get("message", "Die Gegenstelle hat die Verbindung beendet.")
            messagebox.showwarning(
                "Netzwerkverbindung beendet",
                f"Die Mehrspielerpartie wurde unterbrochen.\n\n{detail}",
                parent=self.root,
            )
            self.show_start_screen()
            return False
        return True

    def _start_network_game(self, remote_nickname: str) -> None:
        cleaned = "".join(
            character for character in remote_nickname.strip() if character.isprintable()
        )[:20]
        self.pending_remote_nickname = cleaned or "Gast"
        self.game = KnackGame(2, starting_coins=self.starting_coins)
        self.game.players[0].name = self.nickname
        self.game.players[1].name = self.pending_remote_nickname
        self.game.players[0].is_human = True
        self.game.players[1].is_human = True
        self.selected_hand = None
        self.selected_center = None
        self.message = f"{self.pending_remote_nickname} ist verbunden. Die Partie beginnt."
        self.refresh()
        self._send_host_state()

    def _handle_remote_action(self, message: dict) -> None:
        if self.game is None or self.network_host is None:
            return
        try:
            message_type = message.get("type")
            if message_type == "next_round":
                raise IllegalMove("Nur der Host kann die nächste Runde starten.")
            elif message_type == "action":
                action = message.get("action")
                player_id = 1
                if action == "pass":
                    self.game.pass_turn(player_id)
                elif action == "swap_one":
                    self.game.swap_one(
                        player_id,
                        int(message.get("hand_index", -1)),
                        int(message.get("center_index", -1)),
                    )
                elif action == "swap_all":
                    self.game.swap_all(player_id)
                elif action == "close":
                    self.game.close(player_id)
                elif action == "knack":
                    self.game.knack(player_id)
                elif action == "jackpot":
                    self.game.jackpot(player_id)
                else:
                    raise IllegalMove("Unbekannte Aktion.")
            else:
                raise IllegalMove("Unbekannte Netzwerknachricht.")
        except (IllegalMove, TypeError, ValueError) as exc:
            try:
                self.network_host.send({"type": "error", "message": str(exc)})
            except ConnectionError:
                pass
            return
        self.message = ""
        self.refresh()
        self._send_host_state()

    def _send_host_state(self) -> None:
        if self.network_host is None or self.game is None:
            return
        try:
            self.network_host.send(game_snapshot(self.game, 1))
        except ConnectionError:
            pass

    def _send_client_action(self, action: str, **extra: int) -> None:
        if self.network_client is None or self.awaiting_network:
            return
        try:
            self.network_client.send({"type": "action", "action": action, **extra})
        except ConnectionError as exc:
            self.message = str(exc)
            self.refresh()
            return
        self.awaiting_network = True
        self.message = "Zug wird vom Host bestätigt …"
        self.refresh()

    def _stop_network(self) -> None:
        if self.network_poll_job is not None:
            try:
                self.root.after_cancel(self.network_poll_job)
            except tk.TclError:
                pass
            self.network_poll_job = None
        if self.network_host is not None:
            self.network_host.close()
            self.network_host = None
        if self.network_client is not None:
            self.network_client.close()
            self.network_client = None
        self.network_role = None
        self.awaiting_network = False

    def refresh(self) -> None:
        if self.game is None:
            return
        previous = self.visual_snapshot if self.game_ui_ready else None
        if not self.game_ui_ready:
            self._create_persistent_game_ui()
        self._update_persistent_game_ui()
        current = self._capture_visual_snapshot()
        self.visual_snapshot = current
        self._play_transition_sound(previous, current)
        if previous is None:
            if self.animations_enabled.get() and not self.animation_running:
                self._run_animation_tasks([self._animate_deal])
        else:
            self._animate_transition(previous, current)

    def _create_persistent_game_ui(self) -> None:
        """Baut den Spieltisch einmal auf; spätere Züge ändern nur Inhalte."""

        assert self.game is not None
        self._clear()
        outer = tk.Frame(self.root, bg=BG, padx=18, pady=14)
        outer.place(x=0, y=0, relwidth=1, relheight=1)
        self.screen = outer

        header = tk.Frame(outer, bg=PANEL_2, padx=14, pady=10)
        header.pack(fill="x")
        self.round_label = tk.Label(
            header,
            font=("Segoe UI", 17, "bold"),
            fg=GOLD,
            bg=PANEL_2,
        )
        self.round_label.pack(side="left")
        self.pot_label = tk.Label(
            header,
            font=("Segoe UI", 13, "bold"),
            fg=CREAM,
            bg=PANEL_2,
        )
        self.pot_label.pack(side="right")

        body = tk.Frame(outer, bg=BG)
        body.pack(fill="both", expand=True, pady=(12, 0))
        table = tk.Frame(body, bg=PANEL, padx=18, pady=14)
        table.pack(side="left", fill="both", expand=True)
        sidebar = tk.Frame(body, bg=PANEL_2, width=290, padx=14, pady=14)
        sidebar.pack(side="right", fill="y", padx=(12, 0))
        sidebar.pack_propagate(False)

        opponents_row = tk.Frame(table, bg=PANEL)
        opponents_row.pack(fill="x")
        self.opponent_widgets = {}
        opponents = [
            player
            for player in self.game.players
            if player.id != self.local_player_id
        ]
        opponent_columns = min(4, max(1, len(opponents)))
        for column in range(opponent_columns):
            opponents_row.grid_columnconfigure(column, weight=1, uniform="opponents")
        for display_index, player in enumerate(opponents):
            frame = tk.Frame(opponents_row, bg=PANEL_2, padx=10, pady=8)
            frame.grid(
                row=display_index // opponent_columns,
                column=display_index % opponent_columns,
                sticky="nsew",
                padx=4,
                pady=4,
            )
            title = tk.Label(
                frame,
                font=("Segoe UI", 10, "bold"),
                fg=CREAM,
                bg=PANEL_2,
            )
            title.pack()
            cards_frame = tk.Frame(frame, bg=PANEL_2)
            cards_frame.pack(pady=(7, 0))
            card_labels = []
            for _ in range(3):
                label = tk.Label(
                    cards_frame,
                    text="✦",
                    width=4,
                    height=2,
                    bg="#244d6c",
                    fg=CREAM,
                    relief="ridge",
                    bd=2,
                    font=("Segoe UI", 12, "bold"),
                )
                label.pack(side="left", padx=2)
                card_labels.append(label)
            self.opponent_widgets[player.id] = (
                frame,
                title,
                cards_frame,
                card_labels,
            )

        middle_row = tk.Frame(table, bg=PANEL)
        middle_row.pack(pady=(22, 14))
        center_section = tk.Frame(middle_row, bg=PANEL)
        center_section.pack(side="left")
        tk.Label(
            center_section,
            text="MITTE",
            font=("Segoe UI", 10, "bold"),
            fg=MUTED,
            bg=PANEL,
        ).pack()
        center_cards = tk.Frame(center_section, bg=PANEL)
        center_cards.pack(pady=(5, 0))
        self.center_buttons = []
        for index, card in enumerate(self.game.center):
            button = self._large_card_button(
                center_cards,
                card,
                selected=False,
                enabled=True,
                command=lambda idx=index: self._select_center(idx),
            )
            self.center_buttons.append(button)

        discard_section = tk.Frame(middle_row, bg=PANEL, padx=18)
        discard_section.pack(side="left", padx=(16, 0))
        self.discard_title = tk.Label(
            discard_section,
            text="FRIEDHOF · 0",
            font=("Segoe UI", 10, "bold"),
            fg=MUTED,
            bg=PANEL,
        )
        self.discard_title.pack()
        self.discard_card = tk.Label(
            discard_section,
            text="leer",
            width=7,
            height=3,
            bg="#315149",
            fg=MUTED,
            relief="groove",
            bd=2,
            font=("Segoe UI", 11, "bold"),
        )
        self.discard_card.pack(pady=(5, 0))

        self.human_section = tk.Frame(table, bg=PANEL, padx=8, pady=6)
        self.human_section.pack(pady=(7, 5))
        self.human_title = tk.Label(
            self.human_section,
            font=("Segoe UI", 10, "bold"),
            fg=MUTED,
            bg=PANEL,
        )
        self.human_title.pack()
        self.human_cards_frame = tk.Frame(self.human_section, bg=PANEL)
        self.human_cards_frame.pack(pady=(5, 5))
        self.human_buttons = []
        for index, card in enumerate(self.game.players[self.local_player_id].hand):
            button = self._large_card_button(
                self.human_cards_frame,
                card,
                selected=False,
                enabled=True,
                command=lambda idx=index: self._select_hand(idx),
            )
            self.human_buttons.append(button)
        self.human_score = tk.Label(
            self.human_section,
            font=("Segoe UI", 10, "bold"),
            fg=CREAM,
            bg=PANEL,
        )
        self.human_score.pack()

        action_area = tk.Frame(table, bg=PANEL)
        action_area.pack(fill="x", pady=(13, 0))
        self.action_controls = tk.Frame(action_area, bg=PANEL)
        self.action_controls.pack()
        action_specs = (
            ("pass", "Schieben", self._pass, False),
            ("swap_one", "1 Karte tauschen", self._swap_one, False),
            ("swap_all", "Alle 3 tauschen", self._swap_all, False),
            ("close", "Zumachen", self._close, False),
            ("knack", "KNACK!", self._knack, True),
            ("jackpot", "JACKPOT!", self._jackpot, True),
        )
        self.action_buttons = {}
        for key, text, command, danger in action_specs:
            button = ttk.Button(
                self.action_controls,
                text=text,
                command=command,
                style="Danger.TButton" if danger else "Game.TButton",
            )
            button.pack(side="left", padx=3)
            self.action_buttons[key] = button
        self.turn_message = tk.Label(
            action_area,
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=PANEL,
            wraplength=680,
        )
        self.turn_message.pack(pady=(9, 0))

        self.round_end_frame = tk.Frame(action_area, bg=PANEL)
        self.result_title = tk.Label(
            self.round_end_frame,
            font=("Segoe UI", 16, "bold"),
            fg=GOLD,
            bg=PANEL,
        )
        self.result_title.pack(pady=(4, 7))
        self.result_winners = tk.Label(
            self.round_end_frame,
            font=("Segoe UI", 11, "bold"),
            fg=GOLD,
            bg=PANEL,
        )
        self.result_winners.pack()
        self.result_losers = tk.Label(
            self.round_end_frame,
            font=("Segoe UI", 10, "bold"),
            fg=CREAM,
            bg=PANEL,
        )
        self.result_losers.pack()
        self.next_button = ttk.Button(
            self.round_end_frame,
            style="Accent.TButton",
        )
        self.next_button.pack(pady=(10, 0))

        tk.Label(
            sidebar,
            text="RUNDENPROTOKOLL",
            font=("Segoe UI", 11, "bold"),
            fg=GOLD,
            bg=PANEL_2,
        ).pack(anchor="w")
        self.log_box = tk.Text(
            sidebar,
            bg="#12312b",
            fg=CREAM,
            insertbackground=CREAM,
            relief="flat",
            wrap="word",
            font=("Segoe UI", 9),
            padx=9,
            pady=9,
        )
        self.log_box.pack(fill="both", expand=True, pady=(8, 12))
        tk.Label(
            sidebar,
            text="Kurzmerker",
            font=("Segoe UI", 10, "bold"),
            fg=GOLD,
            bg=PANEL_2,
        ).pack(anchor="w")
        tk.Label(
            sidebar,
            text=(
                "Halbe: 30,5 · AAA verliert ohne Zahlung · 31 ist die "
                "schlechteste Hand · Farbe: ♦ < ♥ < ♠ < ♣"
            ),
            justify="left",
            wraplength=255,
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=PANEL_2,
        ).pack(anchor="w", pady=(4, 0))
        self.game_ui_ready = True

    def _update_persistent_game_ui(self) -> None:
        assert self.game is not None
        game = self.game
        mode = "  ·  LAN" if self.network_role is not None else ""
        self.round_label.configure(text=f"KNACK  ·  Runde {game.round_number}{mode}")
        self.pot_label.configure(text=f"Pot: 🪙 {game.pot}")
        winner_ids = set(game.result.winner_ids) if game.result is not None else set()

        for player in game.players:
            if player.id == self.local_player_id:
                continue
            frame, title, cards_frame, labels = self.opponent_widgets[player.id]
            active_turn = game.current_player_id == player.id
            is_winner = game.round_over and player.id in winner_ids
            frame_bg = WINNER_BG if is_winner else ("#28584c" if active_turn else PANEL_2)
            frame.configure(
                bg=frame_bg,
                highlightthickness=4 if is_winner else (2 if active_turn else 0),
                highlightbackground=GOLD,
            )
            cards_frame.configure(bg=frame_bg)
            status = "ausgeschieden" if not player.active else f"🪙 {player.coins}"
            title_text = (
                f"🏆 RUNDENSIEGER\n{player.name}  ·  {status}"
                if is_winner
                else f"{player.name}  ·  {status}"
            )
            title.configure(
                text=title_text,
                fg=GOLD if is_winner else (CREAM if player.active else MUTED),
                bg=frame_bg,
            )
            for index, label in enumerate(labels):
                label.configure(bg=frame_bg)
                if not game.round_over and player.active:
                    label.configure(
                        text="✦",
                        bg="#244d6c",
                        fg=CREAM,
                        relief="ridge",
                    )
                elif index < len(player.hand):
                    card = player.hand[index]
                    color = RED if card.suit in ("Herz", "Karo") else INK
                    label.configure(
                        text=card.short,
                        bg=CREAM,
                        fg=color,
                        relief="ridge",
                    )
                else:
                    label.configure(text="", relief="flat")

        selectable = self._human_can_act()
        for index, (button, card) in enumerate(zip(self.center_buttons, game.center)):
            self._configure_large_card(
                button,
                card,
                selected=index == self.selected_center,
                enabled=selectable,
            )

        discard_count = len(game.discard)
        self.discard_title.configure(text=f"FRIEDHOF · {discard_count}")
        if game.discard:
            top_card = game.discard[-1]
            color = RED if top_card.suit in ("Herz", "Karo") else INK
            self.discard_card.configure(
                text=f"{top_card.short}\n{top_card.suit}",
                bg=CREAM,
                fg=color,
                relief="solid",
            )
        else:
            self.discard_card.configure(
                text="leer",
                bg="#315149",
                fg=MUTED,
                relief="groove",
            )

        human = game.players[self.local_player_id]
        turn_marker = "  ·  DU BIST AM ZUG" if selectable else ""
        status = "ausgeschieden" if not human.active else f"🪙 {human.coins}"
        human_is_winner = game.round_over and human.id in winner_ids
        human_bg = WINNER_BG if human_is_winner else PANEL
        self.human_section.configure(
            bg=human_bg,
            highlightthickness=4 if human_is_winner else 0,
            highlightbackground=GOLD,
        )
        self.human_cards_frame.configure(bg=human_bg)
        winner_badge = "  ·  🏆 RUNDENSIEGER" if human_is_winner else ""
        self.human_title.configure(
            text=f"DEINE HAND  ·  {status}{turn_marker}{winner_badge}",
            fg=GOLD if selectable or human_is_winner else MUTED,
            bg=human_bg,
        )
        for index, button in enumerate(self.human_buttons):
            if index < len(human.hand):
                self._configure_large_card(
                    button,
                    human.hand[index],
                    selected=index == self.selected_hand,
                    enabled=selectable,
                )
            else:
                button.configure(
                    text="—",
                    state="disabled",
                    bg="#d6d5cf",
                    disabledforeground=MUTED,
                )
        if human.hand:
            self.human_score.configure(
                text=f"Aktuelle Wertung: {evaluate_hand(human.hand).label}",
                bg=human_bg,
            )
        else:
            self.human_score.configure(text="Du bist ausgeschieden.", bg=human_bg)

        if game.round_over:
            self.action_controls.pack_forget()
            self.turn_message.pack_forget()
            if not self.round_end_frame.winfo_manager():
                self.round_end_frame.pack()
            if game.game_over:
                if game.game_winner_id is None:
                    title_text = "Partie beendet: Unentschieden"
                else:
                    title_text = f"{game.players[game.game_winner_id].name} gewinnt die Partie!"
                self.next_button.configure(
                    text="Neues Spiel",
                    command=self.show_start_screen,
                    state="disabled" if self.animation_running else "normal",
                )
            else:
                title_text = f"Runde beendet · {game.result.reason if game.result else ''}"
                if self.network_role == "client":
                    self.next_button.configure(
                        text="Warte auf den Host …",
                        command=lambda: None,
                        state="disabled",
                    )
                else:
                    self.next_button.configure(
                        text="Nächste Runde",
                        command=self._next_round,
                        state="disabled" if self.animation_running else "normal",
                    )
            self.result_title.configure(text=title_text)
            winners = (
                ", ".join(game.players[i].name for i in game.result.winner_ids)
                if game.result
                else ""
            )
            self.result_winners.configure(
                text=f"Rundensieger: {winners}" if winners else ""
            )
            losers = (
                ", ".join(game.players[i].name for i in game.result.loser_ids)
                if game.result
                else ""
            )
            self.result_losers.configure(
                text=f"Rundenverlierer: {losers}" if losers else ""
            )
        else:
            self.round_end_frame.pack_forget()
            if not self.action_controls.winfo_manager():
                self.action_controls.pack()
            if not self.turn_message.winfo_manager():
                self.turn_message.pack(pady=(9, 0))
            actions = game.available_actions(self.local_player_id) if selectable else set()
            self.action_buttons["pass"].configure(text="Schieben")
            enabled = {
                "pass": "pass" in actions,
                "swap_one": (
                    "swap_one" in actions
                    and self.selected_hand is not None
                    and self.selected_center is not None
                ),
                "swap_all": "swap_all" in actions,
                "close": "close" in actions,
                "knack": "knack" in actions,
                "jackpot": "jackpot" in actions,
            }
            for key, button in self.action_buttons.items():
                button.configure(state="normal" if enabled[key] else "disabled")
            if game.closing_remaining is not None:
                hint = (
                    f"Zugabe nach dem Zumachen: noch {game.closing_remaining} "
                    "Spielerzug/-züge."
                )
            elif game.current_player is not None:
                hint = f"Am Zug: {game.current_player.name}"
            else:
                hint = ""
            self.turn_message.configure(
                text=self.message or hint,
                fg="#f4dca0" if self.message else MUTED,
            )

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.insert("1.0", "\n".join(game.log))
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    @staticmethod
    def _configure_large_card(
        button: tk.Button,
        card: Card,
        *,
        selected: bool,
        enabled: bool,
    ) -> None:
        color = RED if card.suit in ("Herz", "Karo") else INK
        button.configure(
            text=f"{card.short}\n{card.suit}",
            bg="#ffe7a3" if selected else CREAM,
            fg=color,
            disabledforeground=color,
            bd=3 if selected else 1,
            state="normal" if enabled else "disabled",
            cursor="hand2" if enabled else "arrow",
        )

    def _capture_visual_snapshot(self) -> dict:
        assert self.game is not None
        local = self.game.players[self.local_player_id]
        return {
            "round": self.game.round_number,
            "round_over": self.game.round_over,
            "center": tuple(self.game.center),
            "discard": tuple(self.game.discard),
            "hand": tuple(local.hand),
            "coins": tuple(player.coins for player in self.game.players),
            "pot": self.game.pot,
            "current": self.game.current_player_id,
            "reason": self.game.result.reason if self.game.result else None,
        }

    def _animate_transition(self, previous: dict, current: dict) -> None:
        if not self.animations_enabled.get() or self.animation_running:
            return
        if previous["round"] != current["round"]:
            self._run_animation_tasks([self._animate_deal])
            return

        tasks: list[Callable[[Callable[[], None]], None]] = []
        if not previous["round_over"] and current["round_over"]:
            if current["reason"] in ("Knack", "Jackpot"):
                tasks.append(self._animate_special_throw)
            tasks.append(self._animate_opponent_reveal)
            tasks.append(self._animate_winner_glow)
            if previous["coins"] != current["coins"]:
                tasks.append(
                    lambda done: self._animate_coin_loss(previous, current, done)
                )
            if current["reason"] in ("Knack", "Jackpot"):
                tasks.append(
                    lambda done: self._animate_special(str(current["reason"]), done)
                )
        elif previous["center"] != current["center"]:
            if previous["hand"] != current["hand"]:
                tasks.append(
                    lambda done: self._animate_card_swap(previous, current, done)
                )
            else:
                tasks.append(
                    lambda done: self._animate_center_change(previous, current, done)
                )

        if (
            not current["round_over"]
            and previous["current"] != current["current"]
        ):
            tasks.append(self._animate_turn_change)

        if tasks:
            self._run_animation_tasks(tasks)

    def _run_animation_tasks(
        self,
        tasks: list[Callable[[Callable[[], None]], None]],
    ) -> None:
        self.animation_running = True
        self._update_persistent_game_ui()
        if self.game and self.game.round_over:
            self.next_button.configure(state="disabled")

        def run(index: int) -> None:
            if index >= len(tasks):
                self.animation_running = False
                if self.game_ui_ready and self.game is not None:
                    self._update_persistent_game_ui()
                return
            tasks[index](lambda: run(index + 1))

        run(0)

    def _toggle_animations(self) -> None:
        if not self.animations_enabled.get():
            self._cancel_animations()

    def _toggle_sounds(self) -> None:
        if not self.sounds_enabled.get() and winsound is not None:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except RuntimeError:
                pass

    @staticmethod
    def _sound_path(name: str) -> str:
        base = getattr(
            sys,
            "_MEIPASS",
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        return os.path.join(base, "assets", "sounds", f"{name}.wav")

    def _play_sound(self, name: str) -> None:
        if not self.sounds_enabled.get() or winsound is None:
            return
        path = self._sound_path(name)
        if not os.path.isfile(path):
            return
        try:
            winsound.PlaySound(
                path,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except RuntimeError:
            pass

    def _play_transition_sound(
        self,
        previous: Optional[dict],
        current: dict,
    ) -> None:
        if previous is None or previous["round"] != current["round"]:
            self._play_sound("deal")
        elif not previous["round_over"] and current["round_over"]:
            reason = current.get("reason")
            self._play_sound(
                "jackpot" if reason == "Jackpot" else "knack" if reason == "Knack" else "win"
            )
        elif previous["coins"] != current["coins"]:
            self._play_sound("coin")
        elif previous["center"] != current["center"] or previous["hand"] != current["hand"]:
            self._play_sound("card")
        elif previous["current"] != current["current"]:
            if not self.animations_enabled.get():
                self._play_sound("turn")

    def _cancel_animations(self, *, restore: bool = True) -> None:
        for job in self.animation_jobs:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self.animation_jobs.clear()
        for overlay in self.animation_overlays:
            try:
                overlay.destroy()
            except tk.TclError:
                pass
        self.animation_overlays.clear()
        self.animation_running = False
        if restore and self.game_ui_ready and self.game is not None:
            self._update_persistent_game_ui()

    def _animation_after(self, delay: int, callback: Callable[[], None]) -> None:
        holder: dict[str, str] = {}

        def wrapped() -> None:
            job = holder.get("job")
            if job in self.animation_jobs:
                self.animation_jobs.remove(job)
            callback()

        holder["job"] = self.root.after(delay, wrapped)
        self.animation_jobs.append(holder["job"])

    def _widget_rect(self, widget: tk.Widget) -> tuple[int, int, int, int]:
        self.root.update_idletasks()
        return (
            widget.winfo_rootx() - self.root.winfo_rootx(),
            widget.winfo_rooty() - self.root.winfo_rooty(),
            max(widget.winfo_width(), 4),
            max(widget.winfo_height(), 4),
        )

    def _floating_card(
        self,
        card: Card,
        rect: tuple[int, int, int, int],
        *,
        back: bool = False,
        compact: bool = False,
    ) -> tk.Label:
        color = RED if card.suit in ("Herz", "Karo") else INK
        label = tk.Label(
            self.root,
            text="✦" if back else (card.short if compact else f"{card.short}\n{card.suit}"),
            bg="#244d6c" if back else CREAM,
            fg=CREAM if back else color,
            relief="solid",
            bd=2,
            font=("Segoe UI", 11 if compact else 14, "bold"),
        )
        x, y, width, height = rect
        label.place(x=x, y=y, width=width, height=height)
        label.lift()
        self.animation_overlays.append(label)
        return label

    def _destroy_overlay(self, overlay: tk.Widget) -> None:
        if overlay in self.animation_overlays:
            self.animation_overlays.remove(overlay)
        try:
            overlay.destroy()
        except tk.TclError:
            pass

    def _move_overlays(
        self,
        moves: list[
            tuple[
                tk.Widget,
                tuple[int, int, int, int],
                tuple[int, int, int, int],
            ]
        ],
        duration_ms: int,
        done: Callable[[], None],
    ) -> None:
        frames = max(10, duration_ms // 18)

        def frame(index: int) -> None:
            progress = min(index / frames, 1.0)
            eased = 1.0 - (1.0 - progress) ** 3
            for overlay, start, end in moves:
                values = [
                    round(start[position] + (end[position] - start[position]) * eased)
                    for position in range(4)
                ]
                overlay.place(
                    x=values[0],
                    y=values[1],
                    width=max(values[2], 2),
                    height=max(values[3], 2),
                )
            if index < frames:
                self._animation_after(18, lambda: frame(index + 1))
            else:
                for overlay, _, _ in moves:
                    self._destroy_overlay(overlay)
                if self.game_ui_ready and self.game is not None:
                    self._update_persistent_game_ui()
                done()

        frame(0)

    def _animate_deal(self, done: Callable[[], None]) -> None:
        """Teilt drei Hände und danach die Mitte in kurzen Stapeln aus."""

        if self.game is None or not self.game.center:
            done()
            return
        center_rect = self._widget_rect(self.center_buttons[0])
        source = (
            max(12, center_rect[0] - 70),
            center_rect[1] + 8,
            48,
            68,
        )
        fallback = self.game.center[0]
        groups: list[list[tuple[Card, tk.Widget, bool, bool]]] = []
        for card_index in range(3):
            group: list[tuple[Card, tk.Widget, bool, bool]] = []
            for player in self.game.players:
                if not player.active:
                    continue
                if player.id == self.local_player_id:
                    if card_index < len(player.hand):
                        group.append(
                            (player.hand[card_index], self.human_buttons[card_index], False, False)
                        )
                elif player.id in self.opponent_widgets:
                    labels = self.opponent_widgets[player.id][3]
                    card = player.hand[card_index] if card_index < len(player.hand) else fallback
                    group.append((card, labels[card_index], not self.game.round_over, True))
            if group:
                groups.append(group)
        groups.append(
            [
                (card, self.center_buttons[index], False, False)
                for index, card in enumerate(self.game.center)
            ]
        )

        def deal_group(index: int) -> None:
            if index >= len(groups):
                done()
                return
            moves = []
            for offset, (card, widget, back, compact) in enumerate(groups[index]):
                start = (source[0] + offset * 2, source[1] + offset * 2, source[2], source[3])
                target = self._widget_rect(widget)
                overlay = self._floating_card(card, start, back=back, compact=compact)
                moves.append((overlay, start, target))
            self._move_overlays(moves, 135, lambda: deal_group(index + 1))

        deal_group(0)

    def _animate_turn_change(self, done: Callable[[], None]) -> None:
        if self.game is None or self.game.current_player_id is None:
            done()
            return
        player_id = self.game.current_player_id
        if player_id == self.local_player_id:
            frame = self.human_section
        elif player_id in self.opponent_widgets:
            frame = self.opponent_widgets[player_id][0]
        else:
            done()
            return
        self._play_sound("turn")
        pulses = ((GOLD, 6), ("#fff1a8", 3), (GOLD, 6), (GOLD, 2))

        def pulse(index: int) -> None:
            if index >= len(pulses):
                if self.game_ui_ready and self.game is not None:
                    self._update_persistent_game_ui()
                done()
                return
            color, width = pulses[index]
            frame.configure(highlightbackground=color, highlightthickness=width)
            self._animation_after(90, lambda: pulse(index + 1))

        pulse(0)

    def _animate_special_throw(self, done: Callable[[], None]) -> None:
        """Wirft die drei Karten des KNACK-/JACKPOT-Rufers in die Mitte."""

        if self.game is None or self.game.result is None:
            done()
            return
        winner_ids = self.game.result.winner_ids
        if not winner_ids:
            done()
            return
        winner_id = winner_ids[0]
        player = self.game.players[winner_id]
        if len(player.hand) < 3:
            done()
            return
        if winner_id == self.local_player_id:
            source_widgets: list[tk.Widget] = list(self.human_buttons)
            compact = False
        elif winner_id in self.opponent_widgets:
            source_widgets = list(self.opponent_widgets[winner_id][3])
            compact = True
        else:
            done()
            return

        moves = []
        for index, (card, widget) in enumerate(zip(player.hand, source_widgets)):
            start = self._widget_rect(widget)
            target = self._widget_rect(self.center_buttons[index])
            widget.configure(text="")
            overlay = self._floating_card(card, start, compact=compact)
            moves.append((overlay, start, target))
        self._move_overlays(moves, 520, done)

    def _animate_card_swap(
        self,
        previous: dict,
        current: dict,
        done: Callable[[], None],
    ) -> None:
        old_hand = list(previous["hand"])
        new_hand = list(current["hand"])
        old_center = list(previous["center"])
        new_center = list(current["center"])
        moves = []
        used_center: set[int] = set()
        for hand_index, new_card in enumerate(new_hand):
            if hand_index >= len(old_hand) or new_card == old_hand[hand_index]:
                continue
            center_index = next(
                (
                    index
                    for index, card in enumerate(old_center)
                    if index not in used_center
                    and card == new_card
                    and index < len(new_center)
                    and new_center[index] == old_hand[hand_index]
                ),
                None,
            )
            if center_index is None:
                continue
            used_center.add(center_index)
            hand_widget = self.human_buttons[hand_index]
            center_widget = self.center_buttons[center_index]
            hand_rect = self._widget_rect(hand_widget)
            center_rect = self._widget_rect(center_widget)
            hand_widget.configure(text="")
            center_widget.configure(text="")
            hand_overlay = self._floating_card(old_hand[hand_index], hand_rect)
            center_overlay = self._floating_card(old_center[center_index], center_rect)
            moves.extend(
                [
                    (hand_overlay, hand_rect, center_rect),
                    (center_overlay, center_rect, hand_rect),
                ]
            )
        if not moves:
            self._animate_center_change(previous, current, done)
            return
        self._move_overlays(moves, 360 if len(moves) == 2 else 520, done)

    def _animate_center_change(
        self,
        previous: dict,
        current: dict,
        done: Callable[[], None],
    ) -> None:
        moves = []
        sent_to_discard = len(current.get("discard", ())) > len(
            previous.get("discard", ())
        )
        discard_rect = self._widget_rect(self.discard_card)
        if sent_to_discard:
            self.discard_card.configure(text="", bg="#315149")
        for index, (old_card, new_card) in enumerate(
            zip(previous["center"], current["center"])
        ):
            if old_card == new_card:
                continue
            widget = self.center_buttons[index]
            rect = self._widget_rect(widget)
            widget.configure(text="")
            x, y, width, height = rect
            upper = (x, y - 75, width, height)
            grave = (
                discard_rect[0] + index * 3,
                discard_rect[1] + index * 2,
                discard_rect[2],
                discard_rect[3],
            )
            old_overlay = self._floating_card(old_card, rect)
            new_overlay = self._floating_card(new_card, upper)
            moves.extend(
                [
                    (old_overlay, rect, grave if sent_to_discard else upper),
                    (new_overlay, upper, rect),
                ]
            )
        if not moves:
            done()
            return
        self._move_overlays(moves, 420, done)

    def _animate_opponent_reveal(self, done: Callable[[], None]) -> None:
        assert self.game is not None
        cards: list[tuple[tk.Label, Card]] = []
        for player in self.game.players:
            if player.id == self.local_player_id:
                continue
            labels = self.opponent_widgets[player.id][3]
            cards.extend(zip(labels, player.hand))
        if not cards:
            done()
            return

        for label, _ in cards:
            label.configure(text="", bg=PANEL_2, relief="flat")

        def flip_one(widget: tk.Label, card: Card) -> None:
            rect = self._widget_rect(widget)
            overlay = self._floating_card(card, rect, back=True, compact=True)
            center_x = rect[0] + rect[2] / 2

            def step(index: int) -> None:
                if index == 5:
                    color = RED if card.suit in ("Herz", "Karo") else INK
                    overlay.configure(text=card.short, bg=CREAM, fg=color)
                scale = max(0.12, abs(index - 5) / 5)
                width = max(3, round(rect[2] * scale))
                overlay.place(
                    x=round(center_x - width / 2),
                    y=rect[1],
                    width=width,
                    height=rect[3],
                )
                if index < 10:
                    self._animation_after(25, lambda: step(index + 1))
                else:
                    self._destroy_overlay(overlay)

            step(0)

        for index, (widget, card) in enumerate(cards):
            self._animation_after(
                index * 115,
                lambda target=widget, value=card: flip_one(target, value),
            )
        total_duration = (len(cards) - 1) * 115 + 320

        def finish() -> None:
            if self.game_ui_ready and self.game is not None:
                self._update_persistent_game_ui()
                self.next_button.configure(state="disabled")
            done()

        self._animation_after(total_duration, finish)

    def _animate_coin_loss(
        self,
        previous: dict,
        current: dict,
        done: Callable[[], None],
    ) -> None:
        destination = self._widget_rect(self.pot_label)
        moves = []
        for player_id, (old_coins, new_coins) in enumerate(
            zip(previous["coins"], current["coins"])
        ):
            lost = max(0, old_coins - new_coins)
            if not lost:
                continue
            source_widget = (
                self.human_title
                if player_id == self.local_player_id
                else self.opponent_widgets[player_id][1]
            )
            source = self._widget_rect(source_widget)
            coin_size = 30
            start = (
                source[0] + source[2] // 2 - coin_size // 2,
                source[1] + source[3] // 2 - coin_size // 2,
                coin_size,
                coin_size,
            )
            end = (
                destination[0] + destination[2] // 2 - coin_size // 2,
                destination[1] + destination[3] // 2 - coin_size // 2,
                coin_size,
                coin_size,
            )
            for offset in range(lost):
                overlay = tk.Label(
                    self.root,
                    text="●",
                    bg=GOLD,
                    fg="#8a6410",
                    relief="solid",
                    bd=2,
                    font=("Segoe UI", 13, "bold"),
                )
                overlay.place(
                    x=start[0] + offset * 5,
                    y=start[1],
                    width=coin_size,
                    height=coin_size,
                )
                overlay.lift()
                self.animation_overlays.append(overlay)
                moves.append((overlay, start, end))
        if not moves:
            done()
            return
        self._play_sound("coin")
        self._move_overlays(moves, 480, done)

    def _animate_winner_glow(self, done: Callable[[], None]) -> None:
        """Lässt alle Rundensieger aufleuchten und belässt die Goldmarkierung."""

        if self.game is None or self.game.result is None:
            done()
            return
        frames: list[tk.Frame] = []
        for player_id in self.game.result.winner_ids:
            if player_id == self.local_player_id:
                frames.append(self.human_section)
            elif player_id in self.opponent_widgets:
                frames.append(self.opponent_widgets[player_id][0])
        if not frames:
            done()
            return

        colors = (GOLD, "#fff1a8", GOLD, "#fff7cf", GOLD)

        def pulse(index: int) -> None:
            if index >= len(colors):
                if self.game_ui_ready and self.game is not None:
                    self._update_persistent_game_ui()
                    self.next_button.configure(state="disabled")
                done()
                return
            for frame in frames:
                frame.configure(
                    highlightbackground=colors[index],
                    highlightthickness=7 if index % 2 else 4,
                )
            self._animation_after(150, lambda: pulse(index + 1))

        pulse(0)

    def _animate_special(self, reason: str, done: Callable[[], None]) -> None:
        text = "JACKPOT!\n●  ●  ●" if reason == "Jackpot" else "KNACK!"
        banner = tk.Label(
            self.root,
            text=text,
            bg=GOLD,
            fg=INK,
            relief="ridge",
            bd=5,
            padx=28,
            pady=14,
            font=("Segoe UI", 26, "bold"),
        )
        banner.place(relx=0.42, rely=0.47, anchor="center")
        banner.lift()
        self.animation_overlays.append(banner)
        sizes = (26, 34, 30, 36, 31)

        def pulse(index: int) -> None:
            if index >= len(sizes):
                self._animation_after(280, finish)
                return
            banner.configure(font=("Segoe UI", sizes[index], "bold"))
            self._animation_after(95, lambda: pulse(index + 1))

        def finish() -> None:
            self._destroy_overlay(banner)
            done()

        pulse(0)

    def _pulse_selected_card(self, button: tk.Button, kind: str, index: int) -> None:
        if not self.animations_enabled.get():
            return
        colors = ("#ffe7a3", "#f2c24f", "#fff0bd", "#ffe7a3")

        def step(position: int) -> None:
            selected = self.selected_hand if kind == "hand" else self.selected_center
            if selected != index or not button.winfo_exists():
                return
            button.configure(bg=colors[position])
            if position + 1 < len(colors):
                self._animation_after(55, lambda: step(position + 1))

        step(0)

    def _build_header(self, parent: tk.Widget) -> None:
        assert self.game is not None
        bar = tk.Frame(parent, bg=PANEL_2, padx=14, pady=10)
        bar.pack(fill="x")
        tk.Label(
            bar,
            text=f"KNACK  ·  Runde {self.game.round_number}",
            font=("Segoe UI", 17, "bold"),
            fg=GOLD,
            bg=PANEL_2,
        ).pack(side="left")
        tk.Label(
            bar,
            text=f"Pot: 🪙 {self.game.pot}",
            font=("Segoe UI", 13, "bold"),
            fg=CREAM,
            bg=PANEL_2,
        ).pack(side="right")

    def _build_opponents(self, parent: tk.Widget) -> None:
        assert self.game is not None
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x")
        opponents = [player for player in self.game.players if not player.is_human]
        for player in opponents:
            active_turn = self.game.current_player_id == player.id
            frame = tk.Frame(
                row,
                bg="#28584c" if active_turn else PANEL_2,
                padx=10,
                pady=8,
                highlightthickness=2 if active_turn else 0,
                highlightbackground=GOLD,
            )
            frame.pack(side="left", fill="x", expand=True, padx=4)
            status = "ausgeschieden" if not player.active else f"🪙 {player.coins}"
            tk.Label(
                frame,
                text=f"{player.name}  ·  {status}",
                font=("Segoe UI", 10, "bold"),
                fg=CREAM if player.active else MUTED,
                bg=frame["bg"],
            ).pack()
            cards = tk.Frame(frame, bg=frame["bg"])
            cards.pack(pady=(7, 0))
            for card in player.hand:
                if self.game.round_over:
                    self._small_card(cards, card)
                else:
                    tk.Label(
                        cards,
                        text="✦",
                        width=4,
                        height=2,
                        bg="#244d6c",
                        fg=CREAM,
                        relief="ridge",
                        bd=2,
                        font=("Segoe UI", 12, "bold"),
                    ).pack(side="left", padx=2)

    def _small_card(self, parent: tk.Widget, card: Card) -> None:
        color = RED if card.suit in ("Herz", "Karo") else INK
        tk.Label(
            parent,
            text=card.short,
            width=4,
            height=2,
            bg=CREAM,
            fg=color,
            relief="ridge",
            bd=2,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=2)

    def _build_center(self, parent: tk.Widget) -> None:
        assert self.game is not None
        section = tk.Frame(parent, bg=PANEL)
        section.pack(pady=(22, 14))
        tk.Label(
            section,
            text="MITTE",
            font=("Segoe UI", 10, "bold"),
            fg=MUTED,
            bg=PANEL,
        ).pack()
        cards = tk.Frame(section, bg=PANEL)
        cards.pack(pady=(5, 0))
        selectable = self._human_can_act()
        for index, card in enumerate(self.game.center):
            self._large_card_button(
                cards,
                card,
                selected=index == self.selected_center,
                enabled=selectable,
                command=lambda idx=index: self._select_center(idx),
            )

    def _build_human_area(self, parent: tk.Widget) -> None:
        assert self.game is not None
        player = self.game.players[0]
        section = tk.Frame(parent, bg=PANEL)
        section.pack(pady=(7, 5))
        turn_marker = "  ·  DU BIST AM ZUG" if self._human_can_act() else ""
        status = "ausgeschieden" if not player.active else f"🪙 {player.coins}"
        tk.Label(
            section,
            text=f"DEINE HAND  ·  {status}{turn_marker}",
            font=("Segoe UI", 10, "bold"),
            fg=GOLD if self._human_can_act() else MUTED,
            bg=PANEL,
        ).pack()
        cards = tk.Frame(section, bg=PANEL)
        cards.pack(pady=(5, 5))
        for index, card in enumerate(player.hand):
            self._large_card_button(
                cards,
                card,
                selected=index == self.selected_hand,
                enabled=self._human_can_act(),
                command=lambda idx=index: self._select_hand(idx),
            )
        if player.hand:
            score = evaluate_hand(player.hand)
            tk.Label(
                section,
                text=f"Aktuelle Wertung: {score.label}",
                font=("Segoe UI", 10, "bold"),
                fg=CREAM,
                bg=PANEL,
            ).pack()

    def _large_card_button(
        self,
        parent: tk.Widget,
        card: Card,
        *,
        selected: bool,
        enabled: bool,
        command: Callable[[], None],
    ) -> tk.Button:
        color = RED if card.suit in ("Herz", "Karo") else INK
        background = "#ffe7a3" if selected else CREAM
        button = tk.Button(
            parent,
            text=f"{card.short}\n{card.suit}",
            width=8,
            height=3,
            bg=background,
            fg=color,
            activebackground="#fff0bd",
            disabledforeground=color,
            relief="solid",
            bd=3 if selected else 1,
            font=("Segoe UI", 14, "bold"),
            command=command,
            cursor="hand2" if enabled else "arrow",
            state="normal" if enabled else "disabled",
        )
        button.pack(side="left", padx=6)
        return button

    def _build_actions(self, parent: tk.Widget) -> None:
        assert self.game is not None
        area = tk.Frame(parent, bg=PANEL)
        area.pack(fill="x", pady=(13, 0))
        if self.game.round_over:
            self._build_round_end(area)
            return

        can_act = self._human_can_act()
        actions = self.game.available_actions(0) if can_act else set()
        buttons = tk.Frame(area, bg=PANEL)
        buttons.pack()
        self._action_button(buttons, "Schieben", "pass" in actions, self._pass)
        self._action_button(
            buttons,
            "1 Karte tauschen",
            "swap_one" in actions
            and self.selected_hand is not None
            and self.selected_center is not None,
            self._swap_one,
        )
        self._action_button(buttons, "Alle 3 tauschen", "swap_all" in actions, self._swap_all)
        self._action_button(buttons, "Zumachen", "close" in actions, self._close)
        self._action_button(buttons, "KNACK!", "knack" in actions, self._knack, danger=True)
        self._action_button(
            buttons, "JACKPOT!", "jackpot" in actions, self._jackpot, danger=True
        )

        if self.game.closing_remaining is not None:
            hint = (
                f"Zugabe nach dem Zumachen: noch {self.game.closing_remaining} "
                "Spielerzug/-züge."
            )
        elif self.game.current_player is not None:
            hint = f"Am Zug: {self.game.current_player.name}"
        else:
            hint = ""
        tk.Label(
            area,
            text=self.message or hint,
            font=("Segoe UI", 10),
            fg="#f4dca0" if self.message else MUTED,
            bg=PANEL,
            wraplength=680,
        ).pack(pady=(9, 0))

    def _action_button(
        self,
        parent: tk.Widget,
        text: str,
        enabled: bool,
        command: Callable[[], None],
        *,
        danger: bool = False,
    ) -> None:
        ttk.Button(
            parent,
            text=text,
            command=command,
            style="Danger.TButton" if danger else "Game.TButton",
            state="normal" if enabled else "disabled",
        ).pack(side="left", padx=3)

    def _build_round_end(self, parent: tk.Widget) -> None:
        assert self.game is not None
        game = self.game
        if game.game_over:
            if game.game_winner_id is None:
                title = "Partie beendet: Unentschieden"
            else:
                title = f"{game.players[game.game_winner_id].name} gewinnt die Partie!"
            button_text = "Neues Spiel"
            command = self.show_start_screen
        else:
            title = f"Runde beendet · {game.result.reason if game.result else ''}"
            button_text = "Nächste Runde"
            command = self._next_round
        tk.Label(
            parent,
            text=title,
            font=("Segoe UI", 16, "bold"),
            fg=GOLD,
            bg=PANEL,
        ).pack(pady=(4, 7))
        if game.result:
            losers = ", ".join(game.players[i].name for i in game.result.loser_ids)
            if losers:
                tk.Label(
                    parent,
                    text=f"Rundenverlierer: {losers}",
                    font=("Segoe UI", 10, "bold"),
                    fg=CREAM,
                    bg=PANEL,
                ).pack()
        ttk.Button(parent, text=button_text, style="Accent.TButton", command=command).pack(
            pady=(10, 0)
        )

    def _build_sidebar(self, parent: tk.Widget) -> None:
        assert self.game is not None
        tk.Label(
            parent,
            text="RUNDENPROTOKOLL",
            font=("Segoe UI", 11, "bold"),
            fg=GOLD,
            bg=PANEL_2,
        ).pack(anchor="w")
        log_box = tk.Text(
            parent,
            bg="#12312b",
            fg=CREAM,
            insertbackground=CREAM,
            relief="flat",
            wrap="word",
            font=("Segoe UI", 9),
            padx=9,
            pady=9,
            state="normal",
        )
        log_box.pack(fill="both", expand=True, pady=(8, 12))
        log_box.insert("1.0", "\n".join(self.game.log))
        log_box.see("end")
        log_box.configure(state="disabled")
        tk.Label(
            parent,
            text="Kurzmerker",
            font=("Segoe UI", 10, "bold"),
            fg=GOLD,
            bg=PANEL_2,
        ).pack(anchor="w")
        tk.Label(
            parent,
            text=(
                "Halbe: 30,5 · AAA verliert ohne Zahlung · 31 ist die "
                "schlechteste Hand · Farbe: ♦ < ♥ < ♠ < ♣"
            ),
            justify="left",
            wraplength=255,
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=PANEL_2,
        ).pack(anchor="w", pady=(4, 0))

    def _human_can_act(self) -> bool:
        return bool(
            self.game
            and not self.game.round_over
            and self.game.current_player_id == self.local_player_id
            and self.game.players[self.local_player_id].active
            and not self.awaiting_network
            and not self.animation_running
        )

    def _select_hand(self, index: int) -> None:
        self.selected_hand = None if self.selected_hand == index else index
        self.message = "Für den Einzeltausch je eine Hand- und Mittelkarte wählen."
        self.refresh()
        if self.selected_hand == index:
            self._play_sound("card")
            self._pulse_selected_card(self.human_buttons[index], "hand", index)

    def _select_center(self, index: int) -> None:
        self.selected_center = None if self.selected_center == index else index
        self.message = "Für den Einzeltausch je eine Hand- und Mittelkarte wählen."
        self.refresh()
        if self.selected_center == index:
            self._play_sound("card")
            self._pulse_selected_card(self.center_buttons[index], "center", index)

    def _perform(self, action: Callable[[], None]) -> None:
        try:
            action()
        except IllegalMove as exc:
            self.message = str(exc)
            self.refresh()
            return
        self.selected_hand = None
        self.selected_center = None
        self.message = ""
        self.refresh()
        if self.network_role == "host":
            self._send_host_state()
        self._schedule_ai_if_needed()

    def _pass(self) -> None:
        assert self.game is not None
        if self.network_role == "client":
            self._send_client_action("pass")
            return
        self._perform(lambda: self.game.pass_turn(self.local_player_id))

    def _swap_one(self) -> None:
        assert self.game is not None
        if self.selected_hand is None or self.selected_center is None:
            self.message = "Bitte zuerst je eine Hand- und Mittelkarte anklicken."
            self.refresh()
            return
        if self.network_role == "client":
            self._send_client_action(
                "swap_one",
                hand_index=self.selected_hand,
                center_index=self.selected_center,
            )
            return
        self._perform(
            lambda: self.game.swap_one(
                self.local_player_id, self.selected_hand, self.selected_center
            )  # type: ignore[arg-type]
        )

    def _swap_all(self) -> None:
        assert self.game is not None
        if self.network_role == "client":
            self._send_client_action("swap_all")
            return
        self._perform(lambda: self.game.swap_all(self.local_player_id))

    def _close(self) -> None:
        assert self.game is not None
        if self.network_role == "client":
            self._send_client_action("close")
            return
        self._perform(lambda: self.game.close(self.local_player_id))

    def _knack(self) -> None:
        assert self.game is not None
        if self.network_role == "client":
            self._send_client_action("knack")
            return
        self._perform(lambda: self.game.knack(self.local_player_id))

    def _jackpot(self) -> None:
        assert self.game is not None
        if self.network_role == "client":
            self._send_client_action("jackpot")
            return
        self._perform(lambda: self.game.jackpot(self.local_player_id))

    def _next_round(self) -> None:
        assert self.game is not None
        if self.animation_running:
            return
        if self.network_role == "client":
            self.message = "Nur der Host kann die nächste Runde starten."
            self.refresh()
            return
        self.game.start_round()
        self.selected_hand = None
        self.selected_center = None
        self.message = ""
        self.refresh()
        if self.network_role == "host":
            self._send_host_state()
        self._schedule_ai_if_needed()

    def _schedule_ai_if_needed(self) -> None:
        if (
            self.game
            and self.network_role is None
            and not self.game.round_over
            and self.game.current_player is not None
            and not self.game.current_player.is_human
        ):
            self.ai_job = self.root.after(650, self._run_ai_turn)

    def _run_ai_turn(self) -> None:
        self.ai_job = None
        if self.game is None or self.game.round_over:
            return
        player = self.game.current_player
        if player is None or player.is_human:
            return

        try:
            if self.game.can_jackpot(player.id):
                self.game.jackpot(player.id)
            elif self.game.can_knack(player.id):
                self.game.knack(player.id)
            else:
                score = evaluate_hand(player.hand)
                can_close = self.game.closing_remaining is None
                very_strong = score.kind == "halbe" or (
                    score.kind == "normal" and score.value >= 29
                )
                if can_close and very_strong and self.game.rng.random() < 0.72:
                    self.game.close(player.id)
                else:
                    action, hand_index, center_index, improved = best_exchange(
                        player.hand, self.game.center
                    )
                    if action == "swap_one":
                        self.game.swap_one(player.id, hand_index, center_index)  # type: ignore[arg-type]
                    elif action == "swap_all":
                        self.game.swap_all(player.id)
                    elif (
                        can_close
                        and score.kind == "normal"
                        and score.value >= 25
                        and self.game.rng.random() < 0.32
                    ):
                        self.game.close(player.id)
                    else:
                        self.game.pass_turn(player.id)
        except (IllegalMove, RuntimeError) as exc:
            messagebox.showerror("Spielzug nicht möglich", str(exc), parent=self.root)
            return

        self.refresh()
        self._schedule_ai_if_needed()

    def show_assumptions(self) -> None:
        messagebox.showinfo("Regelauslegung", ASSUMPTIONS, parent=self.root)

    def show_rules(self) -> None:
        text = (
            "Ziel: Bleibe als letzter Spieler mit Münzen übrig.\n\n"
            "Im Zug: eine Karte tauschen, alle drei tauschen, schieben oder "
            "zumachen. Nach dem Zumachen haben alle anderen noch einen Zug.\n\n"
            "Gewertet wird die beste Kartenfarbe. Halben (drei gleiche) zählen "
            "30,5. AAA verliert ohne Münzzahlung; eine gleichfarbige 31 ist die "
            "schlechteste Hand. Bei vollständigem Gleichstand verlieren alle "
            "beteiligten Spieler.\n\n"
            "Knack: Ass + 10-Punkte-Karte derselben Farbe auf der Hand und "
            "eine weitere passende 10-Punkte-Karte in der Mitte. Die dritte "
            "Handkarte zählt dabei nicht mit.\n"
            "Jackpot: genau zwei Asse + X auf der Hand und ein Ass in der Mitte. "
            "Niemand verliert dabei eine Münze; der Rufer erhält den Pot."
        )
        messagebox.showinfo("Kurzregeln", text, parent=self.root)


def run() -> None:
    root = tk.Tk()
    KnackApp(root)
    root.mainloop()

