import queue
import random
import time
import unittest

from knack.engine import KnackGame
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
        game = KnackGame(2, rng=random.Random(4))
        snapshot = game_snapshot(game, viewer_id=1)
        self.assertEqual(len(snapshot["players"][1]["hand"]), 3)
        self.assertEqual(snapshot["players"][0]["hand"], [])
        self.assertEqual(snapshot["players"][0]["hand_count"], 3)

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
