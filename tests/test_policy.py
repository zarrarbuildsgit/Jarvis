import unittest

from backend.agent.action_schema import Action, ActionType
from backend.security.policy import PolicyDecisionType, PolicyEngine


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.policy = PolicyEngine()

    def test_read_allowed(self):
        action = Action(ActionType.READ_FILE, {"filepath": "README.md"})
        self.assertEqual(self.policy.evaluate(action, trust_level=1).decision, PolicyDecisionType.ALLOW)

    def test_low_trust_write_requires_approval(self):
        action = Action(ActionType.WRITE_FILE, {"filepath": "notes.txt", "content": "hello"}, required_trust=2)
        self.assertEqual(self.policy.evaluate(action, trust_level=1).decision, PolicyDecisionType.REQUIRE_APPROVAL)

    def test_dangerous_terminal_blocked(self):
        action = Action(ActionType.RUN_TERMINAL, {"command": "rm -rf /"}, required_trust=2)
        self.assertEqual(self.policy.evaluate(action, trust_level=4).decision, PolicyDecisionType.BLOCK)

    def test_install_requires_approval(self):
        action = Action(ActionType.RUN_TERMINAL, {"command": "pip install requests"}, required_trust=2)
        self.assertEqual(self.policy.evaluate(action, trust_level=3).decision, PolicyDecisionType.REQUIRE_APPROVAL)


if __name__ == "__main__":
    unittest.main()
