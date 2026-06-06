import unittest

from backend.agent.action_schema import ActionType
from backend.agent.planner import DeterministicPlanner


class TestDeterministicPlanner(unittest.TestCase):
    def setUp(self):
        self.planner = DeterministicPlanner()

    def assert_first_action(self, command, expected):
        plan = self.planner.plan(command)
        self.assertFalse(plan.is_empty, command)
        self.assertEqual(plan.actions[0].type, expected)

    def test_core_commands(self):
        self.assert_first_action("status", ActionType.STATUS)
        self.assert_first_action("list plugins", ActionType.LIST_PLUGINS)
        self.assert_first_action("list files in .", ActionType.LIST_FILES)
        self.assert_first_action("read file README.md", ActionType.READ_FILE)
        self.assert_first_action("create file notes.txt with hello", ActionType.WRITE_FILE)
        self.assert_first_action("press ctrl+s", ActionType.PRESS_KEY)

    def test_windows_sprint3_commands(self):
        self.assert_first_action("list windows", ActionType.LIST_WINDOWS)
        self.assert_first_action("focus window Chrome", ActionType.FOCUS_WINDOW)
        self.assert_first_action("list processes", ActionType.LIST_PROCESSES)
        self.assert_first_action("get clipboard", ActionType.GET_CLIPBOARD)
        self.assert_first_action("set clipboard to hello", ActionType.SET_CLIPBOARD)


if __name__ == "__main__":
    unittest.main()
