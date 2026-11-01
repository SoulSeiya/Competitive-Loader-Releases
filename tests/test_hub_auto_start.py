from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from battle_hub import BattleHub


class AutoStartTests(TestCase):
    def setUp(self):
        self.hub = BattleHub.__new__(BattleHub)
        self.hub.owner = SimpleNamespace(session=None, busy=False, play=Mock())
        self.hub.auto_launch_attempts = set()
        self.hub.status = Mock()
        self.room = dict(self_id=2, users=[dict(id=2, ready=True)],
            tournament=dict(id="cup", current=1, role=2, status="running"))

    def test_ready_assigned_guest_launches_once_even_after_cancel(self):
        for _ in range(5): self.hub.auto_start_match(self.room)
        self.hub.owner.play.assert_called_once_with()

    def test_waiting_or_unready_person_never_launches(self):
        self.room["tournament"]["role"] = 0
        self.hub.auto_start_match(self.room)
        self.room["tournament"]["role"] = 2
        self.room["users"][0]["ready"] = False
        self.hub.auto_start_match(self.room)
        self.hub.owner.play.assert_not_called()

    def test_existing_game_is_reused_and_crash_needs_manual_retry(self):
        self.hub.owner.session = SimpleNamespace(running=True)
        self.hub.auto_start_match(self.room)
        self.room["tournament"]["current"] = 2
        self.hub.auto_start_match(self.room)
        self.hub.owner.session.running = False
        self.hub.auto_start_match(self.room)
        self.hub.owner.play.assert_not_called()

    def test_busy_loader_launches_when_free(self):
        self.hub.owner.busy = True
        self.hub.auto_start_match(self.room)
        self.hub.owner.play.assert_not_called()
        self.hub.owner.busy = False
        self.hub.auto_start_match(self.room)
        self.hub.owner.play.assert_called_once_with()
