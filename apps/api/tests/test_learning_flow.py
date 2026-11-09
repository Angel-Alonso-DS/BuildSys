import unittest
from buildsys_api.service import BuildSysService

class LearningFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = BuildSysService()

    def test_learned_idempotency_rule_transfers_to_returns(self) -> None:
        rule = self.service.learn_from_duplicate("orders")
        built = self.service.build_system("returns")
        first, first_created = self.service.receive_event("returns", "return-100", '{"item":"book"}')
        second, second_created = self.service.receive_event("returns", "return-100", '{"item":"book"}')
        self.assertTrue(rule.validated)
        self.assertEqual(rule.rule_id, built["inherited_rule_id"])
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual("accepted", first["status"])
        self.assertEqual("duplicate_ignored", second["status"])
        self.assertEqual(1, self.service.event_count("returns"))

    def test_request_ids_are_scoped_to_the_system(self) -> None:
        self.service.receive_event("orders", "shared-id", "{}")
        _, created = self.service.receive_event("returns", "shared-id", "{}")
        self.assertTrue(created)
if __name__ == "__main__":
    unittest.main()
