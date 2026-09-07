import unittest

from experimental_rigor_audit.analyze_rigor import (
    LARGE_DATA_RUNS,
    NONIID_RUNS,
    THREAT_DECISIONS,
    THREAT_TRAJECTORIES,
    completeness_audit,
    exact_sign_flip_p,
    holm_adjust,
    read_csv,
)


class RigorAuditTests(unittest.TestCase):
    def test_exact_test_resolution_matches_seed_counts(self) -> None:
        self.assertEqual(exact_sign_flip_p([1.0, 1.0, 1.0]), 0.25)
        self.assertEqual(exact_sign_flip_p([1.0] * 5), 0.0625)

    def test_holm_adjustment_is_monotone_in_sorted_order(self) -> None:
        raw = [0.01, 0.04, 0.02]
        adjusted = holm_adjust(raw)
        ordered = [adjusted[index] for index in sorted(range(3), key=raw.__getitem__)]
        self.assertEqual(ordered, sorted(ordered))
        self.assertTrue(all(0.0 <= value <= 1.0 for value in adjusted))

    def test_saved_core_matrices_are_complete_and_unique(self) -> None:
        audit = completeness_audit(
            read_csv(LARGE_DATA_RUNS),
            read_csv(NONIID_RUNS),
            read_csv(THREAT_TRAJECTORIES),
            read_csv(THREAT_DECISIONS),
        )
        self.assertTrue(audit["all_core_matrices_complete"])
        self.assertTrue(audit["all_primary_keys_unique"])
        self.assertEqual(audit["actual"]["threat_client_decisions"], 1440)


if __name__ == "__main__":
    unittest.main()
