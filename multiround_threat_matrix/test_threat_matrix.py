import csv
import unittest
from pathlib import Path

import torch

from multiround_threat_matrix.run_multiround_threat_matrix import (
    apply_attack,
    build_artifact,
    evaluate_artifact,
    policy_accept,
)


class ThreatMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        raw = {"w": torch.tensor([0.2, -0.1])}
        self.honest = build_artifact(
            raw_update=raw,
            client_id=1,
            round_id=2,
            model_hash="model-a",
            seed=42,
            clip_norm=1.0,
            noise_multiplier=0.08,
        )

    def checks(self, artifact, seen=None):
        return evaluate_artifact(
            artifact,
            expected_client=1,
            expected_round=2,
            expected_model_hash="model-a",
            clip_norm=1.0,
            seen_proofs=set() if seen is None else seen,
        )

    def test_relation_tamper_is_rejected_by_current_gate(self) -> None:
        attacked = apply_attack(
            self.honest,
            "relation_tamper",
            None,
            tamper_amount=0.5,
            clip_bypass_factor=2.0,
            clip_norm=1.0,
        )
        self.assertFalse(policy_accept("current_vdp_gate", self.checks(attacked)))

    def test_clip_bypass_is_forced_over_bound_and_rejected(self) -> None:
        attacked = apply_attack(
            self.honest,
            "clip_bypass",
            None,
            tamper_amount=0.5,
            clip_bypass_factor=2.0,
            clip_norm=1.0,
        )
        checks = self.checks(attacked)
        self.assertGreater(checks["clip_norm_actual"], 1.0)
        self.assertFalse(policy_accept("current_vdp_gate", checks))

    def test_zero_noise_exposes_current_gate_gap(self) -> None:
        attacked = apply_attack(
            self.honest,
            "zero_noise",
            None,
            tamper_amount=0.5,
            clip_bypass_factor=2.0,
            clip_norm=1.0,
        )
        checks = self.checks(attacked)
        self.assertTrue(policy_accept("current_vdp_gate", checks))
        self.assertFalse(policy_accept("strengthened_vdp_gate", checks))

    def test_replay_exposes_context_and_replay_gap(self) -> None:
        checks = evaluate_artifact(
            self.honest,
            expected_client=1,
            expected_round=3,
            expected_model_hash="model-b",
            clip_norm=1.0,
            seen_proofs={self.honest["proof_id"]},
        )
        self.assertTrue(policy_accept("current_vdp_gate", checks))
        self.assertFalse(policy_accept("strengthened_vdp_gate", checks))

    def test_bounded_sign_flip_remains_out_of_scope(self) -> None:
        attacked = apply_attack(
            self.honest,
            "bounded_sign_flip",
            None,
            tamper_amount=0.5,
            clip_bypass_factor=2.0,
            clip_norm=1.0,
        )
        checks = self.checks(attacked)
        self.assertTrue(policy_accept("current_vdp_gate", checks))
        self.assertTrue(policy_accept("strengthened_vdp_gate", checks))
        self.assertFalse(checks["training_provenance_ok"])

    def test_saved_matrix_matches_declared_threat_model(self) -> None:
        result_path = Path(__file__).resolve().parent / "results" / "threat_summary.csv"
        with result_path.open(newline="", encoding="utf-8") as handle:
            rows = {
                (row["attack"], row["policy"]): row
                for row in csv.DictReader(handle)
            }

        def acceptance(attack: str, policy: str) -> float:
            return float(rows[(attack, policy)]["attacker_acceptance_rate_mean"])

        for attack in ("relation_tamper", "clip_bypass"):
            self.assertEqual(acceptance(attack, "current_vdp_gate"), 0.0)
            self.assertEqual(acceptance(attack, "strengthened_vdp_gate"), 0.0)
        for attack in ("replay", "zero_noise"):
            self.assertEqual(acceptance(attack, "current_vdp_gate"), 1.0)
            self.assertEqual(acceptance(attack, "strengthened_vdp_gate"), 0.0)
        self.assertEqual(acceptance("bounded_sign_flip", "current_vdp_gate"), 1.0)
        self.assertEqual(acceptance("bounded_sign_flip", "strengthened_vdp_gate"), 1.0)


if __name__ == "__main__":
    unittest.main()
