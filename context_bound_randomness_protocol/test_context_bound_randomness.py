import copy
import json
import unittest

from context_bound_randomness_protocol.context_bound_randomness import (
    ReferenceCoordinator,
)
from context_bound_randomness_protocol.run_reference_threats import CASES, run_case, setup_bundle


class ContextBoundRandomnessTests(unittest.TestCase):
    def test_all_saved_threat_cases_match_expected_policy(self) -> None:
        rows = [run_case(case) for case in CASES]
        self.assertTrue(all(row["matches_expectation"] for row in rows))

    def test_honest_bundle_is_accepted(self) -> None:
        coordinator, statement, witness = setup_bundle()
        self.assertTrue(coordinator.verify_reference(statement, witness)["accepted"])

    def test_public_statement_hides_secret_seed_and_noise(self) -> None:
        _, statement, witness = setup_bundle()
        public_text = json.dumps(statement, sort_keys=True)
        self.assertNotIn("client_secret", statement)
        self.assertNotIn("noise_seed", statement)
        self.assertNotIn("q_noise", statement)
        self.assertNotIn(witness["client_secret"], public_text)

    def test_replay_consumes_challenge_and_proof(self) -> None:
        coordinator, statement, witness = setup_bundle()
        self.assertTrue(coordinator.verify_reference(statement, witness)["accepted"])
        replay = coordinator.verify_reference(statement, witness)
        self.assertFalse(replay["accepted"])
        self.assertFalse(replay["checks"]["freshness_ok"])
        self.assertFalse(replay["checks"]["replay_ok"])

    def test_zero_noise_is_rejected_even_when_relation_is_valid(self) -> None:
        coordinator, statement, witness = setup_bundle()
        witness["q_noise"] = [0] * len(witness["q_noise"])
        statement["q_noisy"] = list(witness["q_clipped"])
        decision = coordinator.verify_reference(statement, witness)
        self.assertTrue(decision["checks"]["relation_ok"])
        self.assertFalse(decision["checks"]["noise_generation_ok"])
        self.assertFalse(decision["accepted"])

    def test_context_swap_is_rejected(self) -> None:
        coordinator, statement, witness = setup_bundle()
        statement["round_id"] += 1
        decision = coordinator.verify_reference(statement, witness)
        self.assertFalse(decision["checks"]["context_ok"])
        self.assertFalse(decision["accepted"])

    def test_client_cannot_request_multiple_challenges_for_grinding(self) -> None:
        coordinator, statement, _ = setup_bundle()
        with self.assertRaises(ValueError):
            coordinator.issue_challenge(statement["commitment_id"], bytes.fromhex("99" * 32))

    def test_failed_submission_still_consumes_challenge(self) -> None:
        coordinator, statement, witness = setup_bundle()
        tampered = copy.deepcopy(statement)
        tampered["q_noisy"][0] += 1
        self.assertFalse(coordinator.verify_reference(tampered, witness)["accepted"])
        self.assertFalse(coordinator.verify_reference(statement, witness)["accepted"])

    def test_registration_is_setup_time_and_immutable(self) -> None:
        coordinator = ReferenceCoordinator()
        coordinator.register_client(1, "commitment-a")
        with self.assertRaises(ValueError):
            coordinator.register_client(1, "commitment-b")

    def test_statement_requires_commit_before_challenge(self) -> None:
        coordinator = ReferenceCoordinator()
        coordinator.register_client(1, "client-secret-commitment")
        commitment_id = coordinator.commit_update(
            client_id=1,
            round_id=1,
            model_hash="model",
            nonce="nonce",
            commitment="update-commitment",
        )
        with self.assertRaises(ValueError):
            coordinator.build_statement(
                commitment_id=commitment_id,
                q_noisy=[1, 2],
                clip_bound_sq=10,
                noise_k=4,
                noise_unit=1,
            )


if __name__ == "__main__":
    unittest.main()
