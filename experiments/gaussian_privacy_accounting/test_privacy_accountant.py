from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

EXPERIMENTS_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_ROOT))

from gaussian_privacy_accounting.privacy_accountant import (
    gaussian_rdp_epsilon,
    public_deterministic_seed_epsilon,
    rdp_at_order,
    required_raw_noise_multiplier,
)


class PrivacyAccountantTests(unittest.TestCase):
    def test_closed_form_matches_dense_order_search(self) -> None:
        epsilon, alpha = gaussian_rdp_epsilon(
            raw_noise_multiplier=1.2,
            steps=10,
            delta=1e-5,
            adjacency="replace_one",
        )
        orders = [1.001 + index * 0.001 for index in range(1, 100_000)]
        grid_epsilon = min(
            rdp_at_order(
                raw_noise_multiplier=1.2,
                steps=10,
                order=order,
                adjacency="replace_one",
            )
            + math.log(1e5) / (order - 1.0)
            for order in orders
        )
        self.assertAlmostEqual(epsilon, grid_epsilon, places=5)
        self.assertGreater(alpha, 1.0)

    def test_target_epsilon_inversion(self) -> None:
        for target in (1.0, 8.0, 32.0, 128.0):
            noise = required_raw_noise_multiplier(
                target_epsilon=target,
                steps=10,
                delta=1e-5,
                adjacency="replace_one",
            )
            epsilon, _ = gaussian_rdp_epsilon(
                raw_noise_multiplier=noise,
                steps=10,
                delta=1e-5,
                adjacency="replace_one",
            )
            self.assertAlmostEqual(epsilon, target, places=9)

    def test_expected_monotonicity_and_adjacency(self) -> None:
        weak, _ = gaussian_rdp_epsilon(
            raw_noise_multiplier=0.5,
            steps=10,
            delta=1e-5,
            adjacency="replace_one",
        )
        strong, _ = gaussian_rdp_epsilon(
            raw_noise_multiplier=2.0,
            steps=10,
            delta=1e-5,
            adjacency="replace_one",
        )
        fewer_steps, _ = gaussian_rdp_epsilon(
            raw_noise_multiplier=0.5,
            steps=5,
            delta=1e-5,
            adjacency="replace_one",
        )
        add_remove, _ = gaussian_rdp_epsilon(
            raw_noise_multiplier=0.5,
            steps=10,
            delta=1e-5,
            adjacency="add_remove",
        )
        self.assertGreater(weak, strong)
        self.assertGreater(weak, fewer_steps)
        self.assertGreater(weak, add_remove)

    def test_replace_one_requires_twice_the_raw_noise(self) -> None:
        add_remove = required_raw_noise_multiplier(
            target_epsilon=8.0,
            steps=10,
            delta=1e-5,
            adjacency="add_remove",
        )
        replace_one = required_raw_noise_multiplier(
            target_epsilon=8.0,
            steps=10,
            delta=1e-5,
            adjacency="replace_one",
        )
        self.assertAlmostEqual(replace_one, 2.0 * add_remove, places=12)

    def test_public_seed_has_no_finite_epsilon(self) -> None:
        self.assertTrue(math.isinf(public_deterministic_seed_epsilon()))


if __name__ == "__main__":
    unittest.main()
