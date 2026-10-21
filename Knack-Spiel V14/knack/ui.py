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
    game_from_snapshot,
    game_snapshot,
)
from .lobby import DEFAULT_LOBBY_HOST, DEFAULT_LOBBY_PORT, LobbyClient


BG = "#031915"
PANEL = "#062d27"
PANEL_2 = "#0a3930"
CREAM = "#f6f0dc"
INK = "#09231e"
GOLD = "#f2c35d"
GOLD_DARK = "#9f762c"
MUTED = "#b7c4bd"
RED = "#c53f4a"
GREEN = "#155b49"
WINNER_BG = "#5a4920"
CLOSER_BG = "#4b252a"
CLOSER_RED = "#ef5964"
CARD_RANK_FILES = {
    "7": "7",
    "8": "8",
    "9": "9",
    "10": "10",
    "Bube": "bube",
    "Dame": "dame",
    "König": "koenig",
    "Ass": "ass",
}
CARD_SUIT_FILES = {
    "Herz": "herz",
    "Karo": "karo",
    "Kreuz": "kreuz",
    "Pik": "pik",
}
CARD_LARGE_SIZE = (120, 167)
CARD_MEDIUM_SIZE = (72, 100)
CARD_SMALL_SIZE = (44, 62)


ASSUMPTIONS = """Auslegung der im Original offenen Regelstellen

• Tauschen: Erlaubt sind entweder genau eine Handkarte gegen genau eine
  Mittelkarte oder alle drei Handkarten gegen alle drei Mittelkarten.
• Ein Tausch beendet den Zug. Ein erst durch den eigenen Tausch entstandener
  KNACK darf daher nicht sofort im selben Zug gerufen werden.
• Nach dem ersten Zumachen dürfen die folgenden Spieler ebenfalls mit
  zumachen. Dies verbraucht ihren letzten Zug, verlängert die Schlussrunde
  jedoch nicht und startet sie nicht neu.
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
        self.root.title("♠  Knack – Kartenspiel")
        self.root.geometry("1400x880")
        self.root.minsize(1080, 800)
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
        self.lobby_client: Optional[LobbyClient] = None
        self.network_poll_job: Optional[str] = None
        self.awaiting_network = False
        self.nickname = "Spieler"
        self.starting_coins = DEFAULT_STARTING_COINS
        self.pending_remote_nickname = "Gast"
        self.lobby_server_address = f"{DEFAULT_LOBBY_HOST}:{DEFAULT_LOBBY_PORT}"
        self.online_lobbies: list[dict] = []
        self.online_lobby_code = ""
        self.animations_enabled = tk.BooleanVar(value=True)
        self.sounds_enabled = tk.BooleanVar(value=True)
        self.animation_running = False
        self.animation_jobs: list[str] = []
        self.animation_overlays: list[tk.Widget] = []
        self.visual_snapshot: Optional[dict] = None
        self.card_images: dict[str, dict[tuple[str, str], tk.PhotoImage]] = {
            "large": {},
            "medium": {},
            "small": {},
        }
        self.card_back_images: dict[str, tk.PhotoImage] = {}
        self.card_blank_images = {
            "large": tk.PhotoImage(width=CARD_LARGE_SIZE[0], height=CARD_LARGE_SIZE[1]),
            "medium": tk.PhotoImage(width=CARD_MEDIUM_SIZE[0], height=CARD_MEDIUM_SIZE[1]),
            "small": tk.PhotoImage(width=CARD_SMALL_SIZE[0], height=CARD_SMALL_SIZE[1]),
        }
        self.table_background_image = tk.PhotoImage(
            file=self._asset_path("background", "table.png")
        )
        self._load_card_images()
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
            font=("Segoe UI", 12, "bold"),
            foreground=INK,
            background=GOLD,
            bordercolor="#ffe091",
            lightcolor="#ffe091",
            darkcolor=GOLD_DARK,
            focuscolor=GOLD,
            padding=(18, 12),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#ffd574"), ("pressed", "#dca73d")],
            foreground=[("disabled", "#727d77")],
        )
        style.configure(
            "Game.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground=CREAM,
            background="#0a352d",
            bordercolor=GOLD,
            lightcolor=GOLD_DARK,
            darkcolor=GOLD_DARK,
            focuscolor="#0a352d",
            padding=(13, 9),
        )
        style.map(
            "Game.TButton",
            background=[("active", "#155b49"), ("pressed", "#082a24"), ("disabled", "#273c37")],
            foreground=[("disabled", "#7c8984")],
            bordercolor=[("disabled", "#62706a")],
        )
        style.configure(
            "Danger.TButton",
            font=("Segoe UI", 10, "bold"),
            foreground=CREAM,
            background="#612d34",
            bordercolor="#d66a73",
            lightcolor="#d66a73",
            darkcolor="#7e3540",
            padding=(13, 9),
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#8d3945"), ("disabled", "#2e3936")],
            foreground=[("disabled", "#7c8984")],
            bordercolor=[("disabled", "#62706a")],
        )
        style.configure(
            "Knack.TCombobox",
            fieldbackground="#082a24",
            background="#082a24",
            foreground=CREAM,
            arrowcolor=GOLD,
            bordercolor="#55786d",
            lightcolor="#55786d",
            darkcolor="#55786d",
            padding=5,
        )

    @staticmethod
    def _resource_base() -> str:
        return getattr(
            sys,
            "_MEIPASS",
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )

    @classmethod
    def _asset_path(cls, *parts: str) -> str:
        return os.path.join(cls._resource_base(), "assets", *parts)

    def _load_card_images(self) -> None:
        large_folder = self._asset_path("cards", "large")
        small_folder = self._asset_path("cards", "small")
        for rank, rank_file in CARD_RANK_FILES.items():
            for suit, suit_file in CARD_SUIT_FILES.items():
                filename = f"{rank_file}_{suit_file}.png"
                source = tk.PhotoImage(file=os.path.join(large_folder, filename))
                self.card_images["large"][(rank, suit)] = source.zoom(5, 5).subsample(4, 4)
                self.card_images["medium"][(rank, suit)] = source.zoom(3, 3).subsample(4, 4)
                self.card_images["small"][(rank, suit)] = tk.PhotoImage(
                    file=os.path.join(small_folder, filename)
                )
        back_source = tk.PhotoImage(file=os.path.join(large_folder, "back.png"))
        self.card_back_images["large"] = back_source.zoom(5, 5).subsample(4, 4)
        self.card_back_images["medium"] = back_source.zoom(3, 3).subsample(4, 4)
        self.card_back_images["small"] = tk.PhotoImage(
            file=os.path.join(small_folder, "back.png")
        )

    def _card_image(
        self,
        card: Card,
        *,
        compact: bool = False,
        medium: bool = False,
    ) -> tk.PhotoImage:
        size = "small" if compact else "medium" if medium else "large"
        return self.card_images[size][(card.rank, card.suit)]

    def _card_back_image(
        self,
        *,
        compact: bool = False,
        medium: bool = False,
    ) -> tk.PhotoImage:
        size = "small" if compact else "medium" if medium else "large"
        return self.card_back_images[size]

    def _card_blank_image(
        self,
        *,
        compact: bool = False,
        medium: bool = False,
    ) -> tk.PhotoImage:
        size = "small" if compact else "medium" if medium else "large"
        return self.card_blank_images[size]

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

    def _background_root(self) -> tk.Frame:
        """Erzeugt eine Ansicht auf dem gemeinsamen grünen Spieltisch."""

        outer = tk.Frame(self.root, bg=BG)
        outer.place(x=0, y=0, relwidth=1, relheight=1)
        background = tk.Label(
            outer,
            image=self.table_background_image,
            bg=BG,
            bd=0,
            highlightthickness=0,
        )
        background.place(relx=0.5, rely=0.5, anchor="center")
        self.screen = outer
        return outer

    @staticmethod
    def _bordered_panel(
        parent: tk.Widget,
        *,
        background: str = PANEL,
        border: str = GOLD_DARK,
        thickness: int = 1,
    ) -> tuple[tk.Frame, tk.Frame]:
        shell = tk.Frame(parent, bg=border, padx=thickness, pady=thickness)
        panel = tk.Frame(shell, bg=background)
        panel.pack(fill="both", expand=True)
        return shell, panel

    @staticmethod
    def _ornament(
        parent: tk.Widget,
        *,
        text: str = "────────  ♠  ────────",
        background: str = PANEL,
    ) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            font=("Georgia", 12, "bold"),
            fg=GOLD,
            bg=background,
        )

    def _show_start_screen_legacy(self) -> None:
        self._stop_network()
        self._clear()
        self.game = None
        self.local_player_id = 0
        outer = tk.Frame(self.root, bg=BG)
        outer.place(x=0, y=0, relwidth=1, relheight=1)
        self.screen = outer
        card = tk.Frame(outer, bg=PANEL, padx=50, pady=28)
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
                "verbotenen 31. Spiele lokal oder über eine Online-Lobby."
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
            text="ONLINE-LOBBYS",
            font=("Segoe UI", 11, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).pack()
        tk.Label(
            card,
            text=f"Lobbys auf {DEFAULT_LOBBY_HOST} finden oder erstellen.",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=PANEL,
        ).pack(pady=(2, 8))
        ttk.Button(
            card,
            text="Lobby-Browser öffnen",
            style="Game.TButton",
            command=self._open_lobby_browser,
        ).pack(pady=(0, 14))
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

    def show_start_screen(self) -> None:
        self._stop_network()
        self._clear()
        self.game = None
        self.local_player_id = 0
        outer = self._background_root()

        shell, card = self._bordered_panel(outer, background=PANEL, border=GOLD_DARK)
        shell.place(relx=0.5, rely=0.5, anchor="center", width=760, height=760)
        content = tk.Frame(card, bg=PANEL, padx=74, pady=30)
        content.pack(fill="both", expand=True)

        self._ornament(content, text="──────────  ♠  ──────────").pack(pady=(0, 4))
        tk.Label(
            content,
            text="KNACK",
            font=("Georgia", 55, "bold"),
            fg=GOLD,
            bg=PANEL,
        ).pack()
        tk.Label(
            content,
            text="Das Kartenspiel nach euren Hausregeln",
            font=("Segoe UI", 17, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).pack(pady=(0, 24))
        tk.Label(
            content,
            text=(
                "Tausche clever, mache rechtzeitig zu – und hüte dich vor der\n"
                "verbotenen 31. Spiele lokal oder über eine Online-Lobby."
            ),
            justify="center",
            font=("Segoe UI", 12),
            fg=MUTED,
            bg=PANEL,
        ).pack(pady=(0, 24))

        form = tk.Frame(content, bg=PANEL)
        form.pack(fill="x")
        form.grid_columnconfigure(1, weight=1)
        tk.Label(
            form,
            text="Nickname:",
            font=("Segoe UI", 12, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).grid(row=0, column=0, sticky="w", padx=(0, 16), pady=7)
        self.nickname_var = tk.StringVar(value=self.nickname)
        tk.Entry(
            form,
            textvariable=self.nickname_var,
            font=("Segoe UI", 12),
            bg="#082821",
            fg=CREAM,
            insertbackground=GOLD,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#486a60",
            highlightcolor=GOLD,
        ).grid(row=0, column=1, columnspan=3, sticky="ew", ipady=9, pady=7)

        player_count = tk.IntVar(value=3)
        tk.Label(
            form,
            text="Spielerzahl:",
            font=("Segoe UI", 12, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).grid(row=1, column=0, sticky="w", padx=(0, 16), pady=7)
        combo = ttk.Combobox(
            form,
            state="readonly",
            values=tuple(range(MIN_PLAYERS, MAX_PLAYERS + 1)),
            textvariable=player_count,
            width=7,
            font=("Segoe UI", 12),
            style="Knack.TCombobox",
        )
        combo.grid(row=1, column=1, sticky="w", pady=7)
        tk.Label(
            form,
            text="Startmünzen:",
            font=("Segoe UI", 12, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).grid(row=1, column=2, sticky="e", padx=(30, 16), pady=7)
        self.starting_coins_var = tk.StringVar(value=str(self.starting_coins))
        tk.Spinbox(
            form,
            from_=MIN_STARTING_COINS,
            to=MAX_STARTING_COINS,
            textvariable=self.starting_coins_var,
            width=7,
            justify="center",
            font=("Segoe UI", 12),
            bg="#082821",
            fg=CREAM,
            buttonbackground="#174b3f",
            insertbackground=GOLD,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#486a60",
            highlightcolor=GOLD,
        ).grid(row=1, column=3, sticky="e", ipady=5, pady=7)

        ttk.Button(
            content,
            text="▶   Lokales Spiel starten",
            style="Accent.TButton",
            command=lambda: self.start_game(player_count.get()),
            width=31,
        ).pack(pady=(25, 18), ipady=3)

        self._ornament(content, text="────────────  ♠  ────────────").pack(pady=(0, 8))
        tk.Label(
            content,
            text="O N L I N E – L O B B Y S",
            font=("Segoe UI", 12, "bold"),
            fg=GOLD,
            bg=PANEL,
        ).pack()
        tk.Label(
            content,
            text=f"Lobbys auf {DEFAULT_LOBBY_HOST} finden oder erstellen.",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=PANEL,
        ).pack(pady=(7, 12))
        ttk.Button(
            content,
            text="♣   Lobby-Browser öffnen",
            style="Game.TButton",
            command=self._open_lobby_browser,
            width=30,
        ).pack(ipady=3)
        tk.Button(
            content,
            text="Regelauslegung ansehen",
            command=self.show_assumptions,
            relief="flat",
            bg=PANEL,
            fg="#9bd4c3",
            activebackground=PANEL,
            activeforeground=CREAM,
            cursor="hand2",
            font=("Segoe UI", 10, "underline"),
        ).pack(pady=(20, 0))

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

    def _open_lobby_browser(self) -> None:
        nickname = self._validated_nickname()
        if nickname is None:
            return
        self._stop_network()
        host = DEFAULT_LOBBY_HOST
        port = DEFAULT_LOBBY_PORT
        self.lobby_server_address = f"{host}:{port}"
        client = LobbyClient()
        self.lobby_client = client
        self.network_role = "lobby_browser"
        self.local_player_id = 0
        self.online_lobbies = []
        client.connect(host, port)
        self._show_network_waiting(
            "Lobby-Server wird verbunden",
            f"Verbinde mit {host}:{port} …",
        )
        self._schedule_network_poll()

    def _show_lobby_browser_legacy(self) -> None:
        self._clear()
        outer = tk.Frame(self.root, bg=BG, padx=24, pady=22)
        outer.place(x=0, y=0, relwidth=1, relheight=1)
        self.screen = outer

        header = tk.Frame(outer, bg=PANEL_2, padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(
            header,
            text="ONLINE-LOBBYS",
            font=("Segoe UI", 22, "bold"),
            fg=GOLD,
            bg=PANEL_2,
        ).pack(side="left")
        tk.Label(
            header,
            text=f"Server: {self.lobby_server_address}  ·  Nickname: {self.nickname}",
            font=("Segoe UI", 10),
            fg=CREAM,
            bg=PANEL_2,
        ).pack(side="right")

        content = tk.Frame(outer, bg=PANEL, padx=22, pady=20)
        content.pack(fill="both", expand=True, pady=(14, 0))
        tk.Label(
            content,
            text="Verfügbare Partien",
            font=("Segoe UI", 15, "bold"),
            fg=CREAM,
            bg=PANEL,
        ).pack(anchor="w")
        tk.Label(
            content,
            text="Doppelklick auf eine freie Lobby oder unten Beitreten wählen.",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=PANEL,
        ).pack(anchor="w", pady=(2, 10))

        list_frame = tk.Frame(content, bg=PANEL)
        list_frame.pack(fill="both", expand=True)
        self.lobby_listbox = tk.Listbox(
            list_frame,
            bg="#0c221d",
            fg=CREAM,
            selectbackground=GREEN,
            selectforeground=CREAM,
            font=("Consolas", 11),
            relief="flat",
            activestyle="none",
        )
        scrollbar = ttk.Scrollbar(list_frame, command=self.lobby_listbox.yview)
        self.lobby_listbox.configure(yscrollcommand=scrollbar.set)
        self.lobby_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.lobby_listbox.bind("<Double-Button-1>", lambda _event: self._join_selected_lobby())

        self.lobby_empty_label = tk.Label(
            content,
            text="",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=PANEL,
        )
        self.lobby_empty_label.pack(anchor="w", pady=(8, 0))

        controls = tk.Frame(content, bg=PANEL)
        controls.pack(fill="x", pady=(18, 0))
        self.lobby_name_var = tk.StringVar(value=f"{self.nickname}s Runde")
        tk.Entry(
            controls,
            textvariable=self.lobby_name_var,
            width=25,
            font=("Segoe UI", 10),
        ).pack(side="left", ipady=5, padx=(0, 8))
        ttk.Button(
            controls,
            text="Lobby erstellen",
            style="Accent.TButton",
            command=self._create_online_lobby,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            controls,
            text="Beitreten",
            style="Game.TButton",
            command=self._join_selected_lobby,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            controls,
            text="Aktualisieren",
            style="Game.TButton",
            command=self._request_lobby_list,
        ).pack(side="left")
        ttk.Button(
            controls,
            text="Zurück",
            style="Game.TButton",
            command=self.show_start_screen,
        ).pack(side="right")
        self._update_lobby_list()

    def _show_lobby_browser(self) -> None:
        self._clear()
        outer = self._background_root()
        stage = tk.Frame(outer, bg=BG)
        stage.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.88, relheight=0.86)

        header_shell, header = self._bordered_panel(stage, background=PANEL)
        header_shell.pack(fill="x", pady=(0, 14))
        header.configure(padx=30, pady=20)
        header.grid_columnconfigure(1, weight=1)
        tk.Label(
            header,
            text="ONLINE-LOBBYS",
            font=("Georgia", 31, "bold"),
            fg=GOLD,
            bg=PANEL,
        ).grid(row=0, column=0, sticky="w")
        self._ornament(header, text="──────  ♠  ──────").grid(row=0, column=1)
        tk.Label(
            header,
            text=f"Server: {self.lobby_server_address}  ·  Nickname: {self.nickname}",
            font=("Segoe UI", 10),
            fg=CREAM,
            bg=PANEL,
        ).grid(row=0, column=2, sticky="e")

        content_shell, content = self._bordered_panel(stage, background=PANEL)
        content_shell.pack(fill="both", expand=True)
        content.configure(padx=28, pady=22)

        heading = tk.Frame(content, bg=PANEL)
        heading.pack(fill="x")
        tk.Label(
            heading,
            text="♠  Verfügbare Partien",
            font=("Georgia", 22, "bold"),
            fg=GOLD,
            bg=PANEL,
        ).pack(side="left")
        self._ornament(heading, text="──────────  ♦  ──────────").pack(side="left", padx=24)
        tk.Label(
            content,
            text="Doppelklick auf eine freie Lobby oder unten Beitreten wählen.",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=PANEL,
        ).pack(anchor="w", padx=(46, 0), pady=(3, 14))

        list_shell = tk.Frame(content, bg=GOLD_DARK, padx=1, pady=1)
        list_shell.pack(fill="both", expand=True)
        list_frame = tk.Frame(list_shell, bg="#021d19")
        list_frame.pack(fill="both", expand=True)
        self.lobby_listbox = tk.Listbox(
            list_frame,
            bg="#021d19",
            fg=CREAM,
            selectbackground="#1a5c4b",
            selectforeground=CREAM,
            font=("Consolas", 11),
            relief="flat",
            borderwidth=0,
            activestyle="none",
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(list_frame, command=self.lobby_listbox.yview)
        self.lobby_listbox.configure(yscrollcommand=scrollbar.set)
        self.lobby_listbox.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        scrollbar.pack(side="right", fill="y", padx=(0, 3), pady=3)
        self.lobby_listbox.bind(
            "<Double-Button-1>", lambda _event: self._join_selected_lobby()
        )

        info_row = tk.Frame(content, bg=PANEL)
        info_row.pack(fill="x", pady=(12, 12))
        tk.Label(
            info_row,
            text="ⓘ",
            font=("Segoe UI Symbol", 15),
            fg=GOLD,
            bg=PANEL,
        ).pack(side="left")
        self.lobby_empty_label = tk.Label(
            info_row,
            text="",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=PANEL,
        )
        self.lobby_empty_label.pack(side="left", padx=(9, 0))

        tk.Frame(content, bg="#496458", height=1).pack(fill="x", pady=(0, 15))
        controls = tk.Frame(content, bg=PANEL)
        controls.pack(fill="x")
        self.lobby_name_var = tk.StringVar(value=f"{self.nickname}s Runde")
        tk.Entry(
            controls,
            textvariable=self.lobby_name_var,
            width=25,
            font=("Segoe UI", 11),
            bg="#061f1b",
            fg=CREAM,
            insertbackground=GOLD,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#61766d",
            highlightcolor=GOLD,
        ).pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 12))
        ttk.Button(
            controls,
            text="＋  Lobby erstellen",
            style="Accent.TButton",
            command=self._create_online_lobby,
        ).pack(side="left", padx=(0, 9))
        ttk.Button(
            controls,
            text="♣  Beitreten",
            style="Game.TButton",
            command=self._join_selected_lobby,
        ).pack(side="left", padx=(0, 9))
        ttk.Button(
            controls,
            text="⟳  Aktualisieren",
            style="Game.TButton",
            command=self._request_lobby_list,
        ).pack(side="left", padx=(0, 22))
        tk.Frame(controls, bg=GOLD_DARK, width=1).pack(side="left", fill="y", padx=(0, 22))
        ttk.Button(
            controls,
            text="‹  Zurück",
            style="Game.TButton",
            command=self.show_start_screen,
        ).pack(side="right")
        self._update_lobby_list()

    def _update_lobby_list(self) -> None:
        if not hasattr(self, "lobby_listbox") or not self.lobby_listbox.winfo_exists():
            return
        selected_code = ""
        selection = self.lobby_listbox.curselection()
        if selection and selection[0] < len(self.online_lobbies):
            selected_code = str(self.online_lobbies[selection[0]].get("code", ""))
        self.lobby_listbox.delete(0, "end")
        for lobby in self.online_lobbies:
            status = "FREI" if lobby.get("joinable") else "IM SPIEL"
            row = (
                f"{str(lobby.get('name', 'Knack-Runde'))[:30]:<30}  "
                f"Host: {str(lobby.get('host', 'Spieler'))[:20]:<20}  "
                f"{lobby.get('players', 1)}/{lobby.get('capacity', 2)}  {status}"
            )
            self.lobby_listbox.insert("end", row)
            if str(lobby.get("code", "")) == selected_code:
                self.lobby_listbox.selection_set(self.lobby_listbox.size() - 1)
        self.lobby_empty_label.configure(
            text=(
                "Zurzeit ist keine Lobby geöffnet. Erstelle einfach die erste."
                if not self.online_lobbies
                else f"{len(self.online_lobbies)} Lobby(s) gefunden."
            )
        )

    def _request_lobby_list(self) -> None:
        if self.lobby_client is None:
            return
        try:
            self.lobby_client.send({"type": "list_lobbies"})
        except ConnectionError as exc:
            messagebox.showwarning("Lobby-Server", str(exc), parent=self.root)

    def _create_online_lobby(self) -> None:
        if self.lobby_client is None:
            return
        name = self.lobby_name_var.get().strip()[:30]
        if not name:
            messagebox.showinfo("Lobbyname fehlt", "Bitte einen Lobbyname eingeben.", parent=self.root)
            return
        starting_coins = self._validated_starting_coins()
        if starting_coins is None:
            return
        try:
            self.lobby_client.send({"type": "create_lobby", "name": name})
        except ConnectionError as exc:
            messagebox.showwarning("Lobby-Server", str(exc), parent=self.root)

    def _join_selected_lobby(self) -> None:
        if self.lobby_client is None:
            return
        selection = self.lobby_listbox.curselection()
        if not selection:
            messagebox.showinfo("Lobby auswählen", "Bitte zuerst eine Lobby auswählen.", parent=self.root)
            return
        lobby = self.online_lobbies[selection[0]]
        if not lobby.get("joinable"):
            messagebox.showinfo("Lobby ist voll", "Diese Partie läuft bereits.", parent=self.root)
            return
        try:
            self.lobby_client.send({"type": "join_lobby", "code": lobby.get("code", "")})
        except ConnectionError as exc:
            messagebox.showwarning("Lobby-Server", str(exc), parent=self.root)

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

    def _show_network_waiting(self, title: str, detail: str) -> None:
        self._clear()
        outer = self._background_root()
        shell, card = self._bordered_panel(outer, background=PANEL)
        shell.place(relx=0.5, rely=0.48, anchor="center", width=650, height=390)
        card.configure(padx=60, pady=42)
        self._ornament(card).pack(pady=(0, 12))
        tk.Label(
            card,
            text=title,
            font=("Georgia", 27, "bold"),
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
            text="‹  Abbrechen",
            style="Game.TButton",
            command=self.show_start_screen,
        ).pack()

    def _schedule_network_poll(self) -> None:
        if self.network_poll_job is None and self.network_role is not None:
            self.network_poll_job = self.root.after(75, self._poll_network_events)

    def _is_network_host(self) -> bool:
        return self.network_role == "lobby_host"

    def _is_network_client(self) -> bool:
        return self.network_role == "lobby_client"

    def _network_endpoint(self):
        return self.lobby_client

    def _send_game_message(self, message: dict) -> None:
        if self.lobby_client is None:
            raise ConnectionError("Keine Verbindung zum Lobby-Server.")
        self.lobby_client.send({"type": "relay", "payload": message})

    def _poll_network_events(self) -> None:
        self.network_poll_job = None
        endpoint = self._network_endpoint()
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
        if event_type == "connected":
            if self.network_role == "lobby_browser" and self.lobby_client is not None:
                try:
                    self.lobby_client.send({"type": "register", "nickname": self.nickname})
                except ConnectionError as exc:
                    self.message = str(exc)
            return True
        if event_type == "connect_failed":
            detail = (
                f"Der Lobby-Server {DEFAULT_LOBBY_HOST}:{DEFAULT_LOBBY_PORT} konnte "
                "nicht erreicht werden. Prüfe, ob START_LOBBY_SERVER.bat auf dem "
                "Server-PC läuft und der Server-Port erreichbar ist."
            )
            messagebox.showerror(
                "Verbindung fehlgeschlagen",
                f"{detail}\n\n{event.get('message', '')}",
                parent=self.root,
            )
            self.show_start_screen()
            return False
        if event_type == "message":
            message = event.get("message", {})
            message_type = message.get("type")
            if message_type == "registered" and self.network_role == "lobby_browser":
                self._show_lobby_browser()
                return True
            if message_type == "lobby_list":
                self.online_lobbies = [
                    item for item in message.get("lobbies", []) if isinstance(item, dict)
                ]
                self._update_lobby_list()
                return True
            if message_type == "lobby_created":
                self.network_role = "lobby_host"
                self.local_player_id = 0
                self.online_lobby_code = str(message.get("code", ""))
                self._show_network_waiting(
                    "Lobby ist geöffnet",
                    f"{message.get('name', 'Knack-Runde')}\n\n"
                    f"Lobbycode: {self.online_lobby_code}\n\n"
                    "Die Lobby ist jetzt für alle Spieler im Browser sichtbar.\n"
                    "Warte auf Mitspieler …",
                )
                return True
            if message_type == "lobby_joined":
                self.network_role = "lobby_client"
                self.local_player_id = 1
                self.online_lobby_code = str(message.get("code", ""))
                self._show_network_waiting(
                    "Lobby beigetreten",
                    f"{message.get('name', 'Knack-Runde')}\n\n"
                    f"Host: {message.get('host_nickname', 'Spieler')}\n\n"
                    "Der Host bereitet die Partie vor …",
                )
                return True
            if message_type == "peer_joined" and self.network_role == "lobby_host":
                self._start_network_game(str(message.get("nickname", "Gast")))
                return True
            if message_type == "peer_left":
                messagebox.showwarning(
                    "Lobby verlassen",
                    str(message.get("message", "Der Mitspieler hat die Lobby verlassen.")),
                    parent=self.root,
                )
                self.show_start_screen()
                return False
            if message_type == "server_error":
                detail = str(message.get("message", "Anfrage wurde abgelehnt."))
                if self.game is not None:
                    self.awaiting_network = False
                    self.message = detail
                    self.refresh()
                else:
                    messagebox.showwarning("Lobby-Server", detail, parent=self.root)
                return True
            if message_type == "relay":
                message = message.get("payload", {})
                if not isinstance(message, dict):
                    return True

            if self._is_network_host():
                self._handle_remote_action(message)
            elif self._is_network_client() and message.get("type") == "state":
                action_was_pending = self.awaiting_network
                self.game = game_from_snapshot(message)
                self.local_player_id = int(message["viewer_id"])
                self.awaiting_network = False
                if action_was_pending:
                    self.selected_hand = None
                    self.selected_center = None
                self.message = ""
                self.refresh()
            elif self._is_network_client() and message.get("type") == "error":
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
        if self.game is None or not self._is_network_host():
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
                self._send_game_message({"type": "error", "message": str(exc)})
            except ConnectionError:
                pass
            return
        self.message = ""
        self.refresh()
        self._send_host_state()

    def _send_host_state(self) -> None:
        if not self._is_network_host() or self.game is None:
            return
        try:
            self._send_game_message(game_snapshot(self.game, 1))
        except ConnectionError:
            pass

    def _send_client_action(self, action: str, **extra: int) -> None:
        if not self._is_network_client() or self.awaiting_network:
            return
        try:
            self._send_game_message({"type": "action", "action": action, **extra})
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
        if self.lobby_client is not None:
            self.lobby_client.close()
            self.lobby_client = None
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
        outer = self._background_root()
        stage = tk.Frame(outer, bg=BG)
        stage.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.965, relheight=0.95)

        header_shell, header = self._bordered_panel(stage, background=PANEL)
        header_shell.pack(fill="x")
        header.configure(padx=28, pady=14)
        header.grid_columnconfigure(1, weight=1)
        self.round_label = tk.Label(
            header,
            font=("Georgia", 27, "bold"),
            fg=GOLD,
            bg=PANEL,
        )
        self.round_label.grid(row=0, column=0, sticky="w")
        self._ornament(header, text="────────  ♠  ────────").grid(row=0, column=1)
        pot_shell = tk.Frame(header, bg=GOLD_DARK, padx=1, pady=1)
        pot_shell.grid(row=0, column=2, sticky="e")
        self.pot_label = tk.Label(
            pot_shell,
            font=("Georgia", 14, "bold"),
            fg=CREAM,
            bg="#082a24",
            padx=28,
            pady=10,
        )
        self.pot_label.pack()

        body = tk.Frame(stage, bg=BG)
        body.pack(fill="both", expand=True, pady=(12, 0))
        table_shell, table = self._bordered_panel(body, background=PANEL)
        table_shell.pack(side="left", fill="both", expand=True)
        table.configure(padx=22, pady=14)
        sidebar_shell, sidebar = self._bordered_panel(body, background=PANEL)
        sidebar_shell.configure(width=330)
        sidebar_shell.pack(side="right", fill="y", padx=(12, 0))
        sidebar_shell.pack_propagate(False)
        sidebar.configure(padx=18, pady=16)

        opponents_row = tk.Frame(table, bg=PANEL)
        opponents_row.pack(fill="x")
        self.opponent_widgets = {}
        opponents = [
            player
            for player in self.game.players
            if player.id != self.local_player_id
        ]
        self.dense_table_layout = len(opponents) > 4
        opponent_columns = min(4, max(1, len(opponents)))
        for column in range(opponent_columns):
            opponents_row.grid_columnconfigure(column, weight=1, uniform="opponents")
        for display_index, player in enumerate(opponents):
            frame = tk.Frame(
                opponents_row,
                bg=PANEL_2,
                padx=8 if self.dense_table_layout else 10,
                pady=4 if self.dense_table_layout else 8,
                highlightthickness=1,
                highlightbackground="#6e704a",
            )
            frame.grid(
                row=display_index // opponent_columns,
                column=display_index % opponent_columns,
                sticky="nsew",
                padx=4,
                pady=4,
            )
            title = tk.Label(
                frame,
                font=("Georgia", 10, "bold"),
                fg=CREAM,
                bg=PANEL_2,
            )
            title.pack()
            cards_frame = tk.Frame(frame, bg=PANEL_2)
            cards_frame.pack(pady=(2 if self.dense_table_layout else 7, 0))
            card_labels = []
            for _ in range(3):
                card_width, card_height = (
                    CARD_SMALL_SIZE if self.dense_table_layout else CARD_MEDIUM_SIZE
                )
                label = tk.Label(
                    cards_frame,
                    image=self._card_back_image(
                        compact=self.dense_table_layout,
                        medium=not self.dense_table_layout,
                    ),
                    width=card_width,
                    height=card_height,
                    bg=PANEL_2,
                    relief="flat",
                    bd=0,
                    padx=0,
                    pady=0,
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
        middle_row.pack(
            fill="x",
            pady=(8, 3) if self.dense_table_layout else (13, 8)
        )
        center_section = tk.Frame(middle_row, bg=PANEL)
        center_section.pack()
        tk.Label(
            center_section,
            text="────────  M I T T E  ────────",
            font=("Segoe UI", 10, "bold"),
            fg=GOLD,
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

        discard_section = tk.Frame(middle_row, bg=PANEL, padx=8)
        discard_section.place(relx=0.98, rely=0, anchor="ne")
        self.discard_title = tk.Label(
            discard_section,
            text="FRIEDHOF · 0",
            font=("Segoe UI", 10, "bold"),
            fg=CREAM,
            bg=PANEL,
        )
        self.discard_title.pack()
        discard_width, discard_height = (
            CARD_SMALL_SIZE if self.dense_table_layout else CARD_MEDIUM_SIZE
        )
        self.discard_card = tk.Label(
            discard_section,
            text="leer",
            image=self._card_blank_image(
                compact=self.dense_table_layout,
                medium=not self.dense_table_layout,
            ),
            compound="center",
            width=discard_width,
            height=discard_height,
            bg="#173e35",
            fg=MUTED,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground="#718477",
            font=("Segoe UI", 11, "bold"),
        )
        self.discard_card.pack(pady=(5, 0))

        self.human_section = tk.Frame(table, bg=PANEL, padx=8, pady=6)
        self.human_section.pack(
            pady=(2, 1) if self.dense_table_layout else (7, 5)
        )
        self.human_title = tk.Label(
            self.human_section,
            font=("Segoe UI", 10, "bold"),
            fg=GOLD,
            bg=PANEL,
        )
        self.human_title.pack()
        self.human_cards_frame = tk.Frame(self.human_section, bg=PANEL)
        self.human_cards_frame.pack(
            pady=(2, 2) if self.dense_table_layout else (5, 5)
        )
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
        action_area.pack(
            fill="x",
            pady=(5, 0) if self.dense_table_layout else (13, 0),
        )
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
            style_name = (
                "Accent.TButton"
                if key == "pass"
                else "Danger.TButton"
                if danger
                else "Game.TButton"
            )
            button = ttk.Button(
                self.action_controls,
                text=text,
                command=command,
                style=style_name,
            )
            button.pack(side="left", padx=4)
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
            font=("Georgia", 14, "bold"),
            fg=GOLD,
            bg=PANEL,
        ).pack(anchor="w")
        log_shell = tk.Frame(sidebar, bg=GOLD_DARK, padx=1, pady=1)
        log_shell.pack(fill="both", expand=True, pady=(10, 14))
        self.log_box = tk.Text(
            log_shell,
            bg="#031f1b",
            fg=CREAM,
            insertbackground=CREAM,
            relief="flat",
            wrap="word",
            font=("Segoe UI", 9),
            padx=9,
            pady=9,
        )
        self.log_box.pack(fill="both", expand=True)
        self._ornament(sidebar, text="────────  ♠  ────────").pack(fill="x", pady=(0, 10))
        tk.Label(
            sidebar,
            text="Kurzmerker",
            font=("Georgia", 12, "bold"),
            fg=GOLD,
            bg=PANEL,
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
            bg=PANEL,
        ).pack(anchor="w", pady=(4, 0))
        self.game_ui_ready = True

    def _update_persistent_game_ui(self) -> None:
        assert self.game is not None
        game = self.game
        if self.network_role in ("lobby_host", "lobby_client"):
            mode = "  ·  ONLINE"
        else:
            mode = ""
        self.round_label.configure(text=f"KNACK  ·  Runde {game.round_number}{mode}")
        self.pot_label.configure(text=f"Pot: 🪙 {game.pot}")
        winner_ids = set(game.result.winner_ids) if game.result is not None else set()
        closer_ids = set(game.closing_player_ids) if not game.round_over else set()

        for player in game.players:
            if player.id == self.local_player_id:
                continue
            frame, title, cards_frame, labels = self.opponent_widgets[player.id]
            active_turn = game.current_player_id == player.id
            is_winner = game.round_over and player.id in winner_ids
            is_closer = player.id in closer_ids
            frame_bg = (
                WINNER_BG
                if is_winner
                else CLOSER_BG
                if is_closer
                else "#28584c"
                if active_turn
                else PANEL_2
            )
            frame.configure(
                bg=frame_bg,
                highlightthickness=4 if is_winner or is_closer else (2 if active_turn else 1),
                highlightbackground=(
                    GOLD
                    if is_winner
                    else CLOSER_RED
                    if is_closer
                    else GOLD
                    if active_turn
                    else "#6e704a"
                ),
            )
            cards_frame.configure(bg=frame_bg)
            status = "ausgeschieden" if not player.active else f"🪙 {player.coins}"
            if is_winner:
                title_text = f"🏆 RUNDENSIEGER\n{player.name}  ·  {status}"
            elif is_closer:
                title_text = f"🔒 ZUGEMACHT\n{player.name}  ·  {status}"
            else:
                title_text = f"{player.name}  ·  {status}"
            title.configure(
                text=title_text,
                fg=GOLD if is_winner else CLOSER_RED if is_closer else (CREAM if player.active else MUTED),
                bg=frame_bg,
            )
            for index, label in enumerate(labels):
                label.configure(bg=frame_bg)
                if not game.round_over and player.active:
                    label.configure(
                        text="",
                        image=self._card_back_image(
                            compact=self.dense_table_layout,
                            medium=not self.dense_table_layout,
                        ),
                        bg=frame_bg,
                        relief="flat",
                    )
                elif index < len(player.hand):
                    card = player.hand[index]
                    label.configure(
                        text="",
                        image=self._card_image(
                            card,
                            compact=self.dense_table_layout,
                            medium=not self.dense_table_layout,
                        ),
                        bg=frame_bg,
                        relief="flat",
                    )
                else:
                    label.configure(
                        text="",
                        image=self._card_blank_image(
                            compact=self.dense_table_layout,
                            medium=not self.dense_table_layout,
                        ),
                        relief="flat",
                    )

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
            self.discard_card.configure(
                text="",
                image=self._card_image(
                    top_card,
                    compact=self.dense_table_layout,
                    medium=not self.dense_table_layout,
                ),
                bg=PANEL,
                relief="flat",
            )
        else:
            self.discard_card.configure(
                text="leer",
                image=self._card_blank_image(
                    compact=self.dense_table_layout,
                    medium=not self.dense_table_layout,
                ),
                compound="center",
                bg="#315149",
                fg=MUTED,
                relief="groove",
            )

        human = game.players[self.local_player_id]
        turn_marker = "  ·  DU BIST AM ZUG" if selectable else ""
        status = "ausgeschieden" if not human.active else f"🪙 {human.coins}"
        human_is_winner = game.round_over and human.id in winner_ids
        human_is_closer = human.id in closer_ids
        human_bg = WINNER_BG if human_is_winner else CLOSER_BG if human_is_closer else PANEL
        self.human_section.configure(
            bg=human_bg,
            highlightthickness=4 if human_is_winner or human_is_closer else 0,
            highlightbackground=GOLD if human_is_winner else CLOSER_RED,
        )
        self.human_cards_frame.configure(bg=human_bg)
        winner_badge = "  ·  🏆 RUNDENSIEGER" if human_is_winner else ""
        closer_badge = "  ·  🔒 ZUGEMACHT" if human_is_closer else ""
        self.human_title.configure(
            text=f"────  DEINE HAND  ·  {status}{turn_marker}{winner_badge}{closer_badge}  ────",
            fg=GOLD if selectable or human_is_winner else CLOSER_RED if human_is_closer else MUTED,
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
                    image=self._card_blank_image(),
                    compound="center",
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
                if self._is_network_client():
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
            self.action_buttons["close"].configure(
                text="Mit zumachen" if game.closing_remaining is not None else "Zumachen"
            )
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
                closer_names = ", ".join(
                    game.players[player_id].name for player_id in game.closing_player_ids
                )
                close_verb = "hat" if len(game.closing_player_ids) == 1 else "haben"
                turns = (
                    "1 Spielerzug"
                    if game.closing_remaining == 1
                    else f"{game.closing_remaining} Spielerzüge"
                )
                hint = (
                    f"Schlussrunde: {closer_names} {close_verb} zugemacht · noch "
                    f"{turns}. Mit-Zumachen ist erlaubt."
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

    def _configure_large_card(
        self,
        button: tk.Button,
        card: Card,
        *,
        selected: bool,
        enabled: bool,
    ) -> None:
        button.configure(
            text="",
            image=self._card_image(card),
            width=CARD_LARGE_SIZE[0],
            height=CARD_LARGE_SIZE[1],
            bg=GOLD if selected else PANEL,
            activebackground=GOLD if selected else PANEL_2,
            bd=4,
            relief="flat",
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
            "closers": tuple(self.game.closing_player_ids),
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

        if not current["round_over"] and previous["closers"] != current["closers"]:
            tasks.append(
                lambda done: self._animate_close_glow(previous, current, done)
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

    @classmethod
    def _sound_path(cls, name: str) -> str:
        return cls._asset_path("sounds", f"{name}.wav")

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
        image = (
            self._card_back_image(compact=compact)
            if back
            else self._card_image(card, compact=compact)
        )
        label = tk.Label(
            self.root,
            text="",
            image=image,
            bg=BG,
            relief="flat",
            bd=0,
            padx=0,
            pady=0,
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

    def _animate_close_glow(
        self,
        previous: dict,
        current: dict,
        done: Callable[[], None],
    ) -> None:
        new_ids = [
            player_id
            for player_id in current["closers"]
            if player_id not in previous["closers"]
        ]
        frames: list[tk.Frame] = []
        for player_id in new_ids:
            if player_id == self.local_player_id:
                frames.append(self.human_section)
            elif player_id in self.opponent_widgets:
                frames.append(self.opponent_widgets[player_id][0])
        if not frames:
            done()
            return
        pulses = ((CLOSER_RED, 7), ("#ffb0b6", 4), (CLOSER_RED, 7), (CLOSER_RED, 4))

        def pulse(index: int) -> None:
            if index >= len(pulses):
                if self.game_ui_ready and self.game is not None:
                    self._update_persistent_game_ui()
                done()
                return
            color, width = pulses[index]
            for frame in frames:
                frame.configure(highlightbackground=color, highlightthickness=width)
            self._animation_after(125, lambda: pulse(index + 1))

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
            widget.configure(text="", image=self._card_blank_image(compact=compact))
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
            hand_widget.configure(text="", image=self._card_blank_image())
            center_widget.configure(text="", image=self._card_blank_image())
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
            self.discard_card.configure(
                text="",
                image=self._card_blank_image(compact=True),
                bg="#315149",
            )
        for index, (old_card, new_card) in enumerate(
            zip(previous["center"], current["center"])
        ):
            if old_card == new_card:
                continue
            widget = self.center_buttons[index]
            rect = self._widget_rect(widget)
            widget.configure(text="", image=self._card_blank_image())
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
            label.configure(
                text="",
                image=self._card_blank_image(compact=True),
                bg=PANEL_2,
                relief="flat",
            )

        def flip_one(widget: tk.Label, card: Card) -> None:
            rect = self._widget_rect(widget)
            overlay = self._floating_card(card, rect, back=True, compact=True)
            center_x = rect[0] + rect[2] / 2

            def step(index: int) -> None:
                if index == 5:
                    overlay.configure(
                        text="",
                        image=self._card_image(card, compact=True),
                        bg=BG,
                    )
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
                        image=self._card_back_image(compact=True),
                        width=CARD_SMALL_SIZE[0],
                        height=CARD_SMALL_SIZE[1],
                        bg=frame["bg"],
                        relief="flat",
                        bd=0,
                    ).pack(side="left", padx=2)

    def _small_card(self, parent: tk.Widget, card: Card) -> None:
        tk.Label(
            parent,
            text="",
            image=self._card_image(card, compact=True),
            width=CARD_SMALL_SIZE[0],
            height=CARD_SMALL_SIZE[1],
            bg=PANEL,
            relief="flat",
            bd=0,
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
        background = GOLD if selected else PANEL
        button = tk.Button(
            parent,
            text="",
            image=self._card_image(card),
            width=CARD_LARGE_SIZE[0],
            height=CARD_LARGE_SIZE[1],
            bg=background,
            activebackground=GOLD if selected else PANEL_2,
            relief="flat",
            bd=4,
            padx=0,
            pady=0,
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
        self._action_button(
            buttons,
            "Mit zumachen" if self.game.closing_remaining is not None else "Zumachen",
            "close" in actions,
            self._close,
        )
        self._action_button(buttons, "KNACK!", "knack" in actions, self._knack, danger=True)
        self._action_button(
            buttons, "JACKPOT!", "jackpot" in actions, self._jackpot, danger=True
        )

        if self.game.closing_remaining is not None:
            closer_names = ", ".join(
                self.game.players[player_id].name
                for player_id in self.game.closing_player_ids
            )
            close_verb = "hat" if len(self.game.closing_player_ids) == 1 else "haben"
            turns = (
                "1 Spielerzug"
                if self.game.closing_remaining == 1
                else f"{self.game.closing_remaining} Spielerzüge"
            )
            hint = (
                f"Schlussrunde: {closer_names} {close_verb} zugemacht · noch "
                f"{turns}. "
                "Mit-Zumachen ist erlaubt."
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
        if self._is_network_host():
            self._send_host_state()
        self._schedule_ai_if_needed()

    def _pass(self) -> None:
        assert self.game is not None
        if self._is_network_client():
            self._send_client_action("pass")
            return
        self._perform(lambda: self.game.pass_turn(self.local_player_id))

    def _swap_one(self) -> None:
        assert self.game is not None
        if self.selected_hand is None or self.selected_center is None:
            self.message = "Bitte zuerst je eine Hand- und Mittelkarte anklicken."
            self.refresh()
            return
        if self._is_network_client():
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
        if self._is_network_client():
            self._send_client_action("swap_all")
            return
        self._perform(lambda: self.game.swap_all(self.local_player_id))

    def _close(self) -> None:
        assert self.game is not None
        if self._is_network_client():
            self._send_client_action("close")
            return
        self._perform(lambda: self.game.close(self.local_player_id))

    def _knack(self) -> None:
        assert self.game is not None
        if self._is_network_client():
            self._send_client_action("knack")
            return
        self._perform(lambda: self.game.knack(self.local_player_id))

    def _jackpot(self) -> None:
        assert self.game is not None
        if self._is_network_client():
            self._send_client_action("jackpot")
            return
        self._perform(lambda: self.game.jackpot(self.local_player_id))

    def _next_round(self) -> None:
        assert self.game is not None
        if self.animation_running:
            return
        if self._is_network_client():
            self.message = "Nur der Host kann die nächste Runde starten."
            self.refresh()
            return
        self.game.start_round()
        self.selected_hand = None
        self.selected_center = None
        self.message = ""
        self.refresh()
        if self._is_network_host():
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
                can_close = "close" in self.game.available_actions(player.id)
                joining_close = self.game.closing_remaining is not None
                very_strong = score.kind == "halbe" or (
                    score.kind == "normal" and score.value >= 29
                )
                if joining_close and can_close and very_strong and self.game.rng.random() < 0.55:
                    self.game.close(player.id)
                elif (
                    not joining_close
                    and can_close
                    and very_strong
                    and self.game.rng.random() < 0.72
                ):
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
            "zumachen. Nach dem Zumachen haben alle anderen noch einen Zug. "
            "Sie können mit dem entsprechend umbenannten Button ebenfalls "
            "zumachen, ohne die Schlussrunde zu verlängern.\n\n"
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

