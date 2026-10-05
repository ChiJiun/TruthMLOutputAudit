import unittest

import numpy as np

from noniid_client_scaling.run_noniid_client_scaling import (
    dirichlet_client_indices,
    partition_diagnostics,
)


class NonIIDPartitionTests(unittest.TestCase):
    def test_dirichlet_partition_is_deterministic_and_complete(self) -> None:
        labels = np.repeat(np.arange(7), 1000)
        first = dirichlet_client_indices(labels, clients=10, alpha=0.5, seed=42, min_client_size=20)
        second = dirichlet_client_indices(labels, clients=10, alpha=0.5, seed=42, min_client_size=20)
        self.assertEqual(len(first), 10)
        self.assertTrue(all(np.array_equal(a, b) for a, b in zip(first, second)))
        combined = np.concatenate(first)
        self.assertEqual(len(combined), len(labels))
        self.assertEqual(len(np.unique(combined)), len(labels))

    def test_low_alpha_produces_measurable_label_skew(self) -> None:
        labels = np.repeat(np.arange(7), 2000)
        groups = dirichlet_client_indices(labels, clients=10, alpha=0.1, seed=52, min_client_size=20)
        diagnostics = partition_diagnostics(labels, groups, num_classes=7)
        self.assertGreater(diagnostics["label_tv_mean"], 0.2)
        self.assertLess(diagnostics["label_entropy_mean"], 0.8)

    def test_invalid_alpha_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            dirichlet_client_indices(np.arange(100) % 2, clients=2, alpha=0, seed=1)


if __name__ == "__main__":
    unittest.main()
