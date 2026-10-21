import queue
import random
import time
import unittest

from knack.engine import Card, KnackGame
from knack.network import LanClient, LanHost, game_from_snapshot, game_snapshot


def wait_for_event(events, expected, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            event = events.get(timeout=0.1)
        except queue.Empty:
            continue
        if event.get("event") == expected:
            return event
    raise AssertionError(f"Netzwerkereignis {expected!r} nicht empfangen")


class SnapshotTests(unittest.TestCase):
    def test_snapshot_hides_opponent_hand_during_round(self):
        game = KnackGame(2, starting_coins=6, rng=random.Random(4))
        snapshot = game_snapshot(game, viewer_id=1)
        self.assertEqual(len(snapshot["players"][1]["hand"]), 3)
        self.assertEqual(snapshot["players"][0]["hand"], [])
        self.assertEqual(snapshot["players"][0]["hand_count"], 3)
        self.assertEqual(snapshot["starting_coins"], 6)
        self.assertEqual(game_from_snapshot(snapshot).starting_coins, 6)

    def test_snapshot_round_trip_preserves_public_state(self):
        game = KnackGame(2, rng=random.Random(7))
        game.players[0].name = "Alice"
        game.players[1].name = "Bob"
        game.close(0)
        game.pass_turn(1)
        snapshot = game_snapshot(game, viewer_id=1)
        mirror = game_from_snapshot(snapshot)
        self.assertTrue(mirror.round_over)
        self.assertEqual(mirror.pot, game.pot)
        self.assertEqual(mirror.result.reason, game.result.reason)
        self.assertEqual(mirror.result.loser_ids, game.result.loser_ids)
        self.assertEqual(mirror.players[0].hand, game.players[0].hand)
        self.assertEqual(mirror.players[1].hand, game.players[1].hand)
        self.assertEqual([player.name for player in mirror.players], ["Alice", "Bob"])

    def test_discard_pile_is_synchronized(self):
        game = KnackGame(2, rng=random.Random(12))
        old_center = tuple(game.center)
        game.pass_turn(0)
        game.pass_turn(1)
        self.assertEqual(tuple(game.discard), old_center)
        mirror = game_from_snapshot(game_snapshot(game, viewer_id=1))
        self.assertEqual(mirror.discard, game.discard)

    def test_join_close_state_and_action_are_synchronized(self):
        game = KnackGame(3, rng=random.Random(15))
        game.close(0)
        mirror = game_from_snapshot(game_snapshot(game, viewer_id=1))
        self.assertEqual(mirror.closing_player_id, 0)
        self.assertEqual(mirror.closing_player_ids, [0])
        self.assertEqual(mirror.closing_remaining, 2)
        self.assertIn("close", mirror.available_actions(1))

    def test_snapshot_does_not_grant_extra_knack_action_after_swap(self):
        game = KnackGame(2, auto_deal=False)
        game.players[0].hand = [
            Card("Ass", "Herz"),
            Card("König", "Herz"),
            Card("Dame", "Herz"),
        ]
        game.players[1].hand = [
            Card("7", "Kreuz"),
            Card("8", "Kreuz"),
            Card("9", "Kreuz"),
        ]
        game.center = [
            Card("7", "Karo"),
            Card("8", "Pik"),
            Card("Dame", "Karo"),
        ]
        game.turn_order = [0, 1]
        game.turn_pos = 0
        game.round_over = False

        game.swap_one(0, 2, 0)
        mirror = game_from_snapshot(game_snapshot(game, viewer_id=0))

        self.assertEqual(mirror.current_player_id, 1)
        self.assertEqual(mirror.available_actions(0), set())

    def test_guest_can_detect_knack_with_ignored_third_suited_card(self):
        game = KnackGame(2, rng=random.Random(14))
        game.players[1].hand = [
            Card("Ass", "Herz"),
            Card("Dame", "Herz"),
            Card("7", "Herz"),
        ]
        game.center = [
            Card("König", "Herz"),
            Card("8", "Pik"),
            Card("9", "Karo"),
        ]
        game.turn_pos = game.turn_order.index(1)

        guest = game_from_snapshot(game_snapshot(game, viewer_id=1))

        self.assertTrue(guest.can_knack(1))
        self.assertIn("knack", guest.available_actions(1))


class SocketProtocolTests(unittest.TestCase):
    def test_host_and_client_exchange_json_messages(self):
        host = LanHost(0)
        client = LanClient()
        try:
            host.start()
            client.connect("127.0.0.1", host.port)
            wait_for_event(client.events, "connected")
            wait_for_event(host.events, "connected")

            client.send({"type": "action", "action": "pass"})
            incoming = wait_for_event(host.events, "message")
            self.assertEqual(incoming["message"]["action"], "pass")

            host.send({"type": "state", "round_number": 1})
            reply = wait_for_event(client.events, "message")
            self.assertEqual(reply["message"]["type"], "state")
            self.assertEqual(reply["message"]["round_number"], 1)
        finally:
            client.close()
            host.close()


if __name__ == "__main__":
    unittest.main()
