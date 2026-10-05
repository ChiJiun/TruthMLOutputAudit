import itertools
import math
import sys
import unittest
from pathlib import Path

EXPERIMENTS_ROOT = Path(__file__).resolve().parents[1]
if str(EXPERIMENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_ROOT))

from discrete_noise_accounting.centered_binomial_accountant import (
    ComposedPrivacyProfile,
    account,
    centered_binomial_pmf,
    scalar_hockey_stick_delta,
)


class CenteredBinomialAccountantTests(unittest.TestCase):
    def test_pmf_is_normalized_and_symmetric(self) -> None:
        pmf = centered_binomial_pmf(16)
        self.assertAlmostEqual(sum(pmf.values()), 1.0, places=15)
        for value, probability in pmf.items():
            self.assertEqual(probability, pmf[-value])

    def test_one_composition_upper_bounds_direct_hockey_stick(self) -> None:
        profile = ComposedPrivacyProfile(
            k=16, shift=2, compositions=1, grid_step=0.0005, numerical_guard=1e-12
        )
        for epsilon in (0.0, 0.5, 1.0, 2.0, 4.0):
            self.assertGreaterEqual(
                profile.delta_upper(epsilon) + 1e-14,
                scalar_hockey_stick_delta(16, 2, epsilon),
            )

    def test_two_compositions_upper_bound_exact_product_distribution(self) -> None:
        k = 4
        shift = 2
        pmf = centered_binomial_pmf(k)
        profile = ComposedPrivacyProfile(
            k=k, shift=shift, compositions=2, grid_step=0.0005, numerical_guard=1e-12
        )

        def exact(direction: int, epsilon: float) -> float:
            total = 0.0
            for left, right in itertools.product(pmf, repeat=2):
                probability = pmf[left] * pmf[right]
                neighbor = pmf.get(left - direction, 0.0) * pmf.get(right - direction, 0.0)
                total += max(probability - math.exp(epsilon) * neighbor, 0.0)
            return total

        for epsilon in (0.0, 0.5, 1.0, 2.0):
            exact_delta = max(exact(shift, epsilon), exact(-shift, epsilon))
            self.assertGreaterEqual(profile.delta_upper(epsilon) + 1e-13, exact_delta)

    def test_maximum_allowed_shift_dominates_scalar_profile(self) -> None:
        for epsilon in (0.0, 0.5, 1.0, 2.0, 4.0):
            self.assertGreaterEqual(
                scalar_hockey_stick_delta(16, 2, epsilon),
                scalar_hockey_stick_delta(16, 1, epsilon),
            )

    def test_delta_is_monotone_in_epsilon(self) -> None:
        profile = ComposedPrivacyProfile(k=16, shift=2, compositions=40)
        values = [profile.delta_upper(epsilon) for epsilon in (0, 2, 4, 8, 16, 32)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_primary_circuit_profile_has_finite_epsilon(self) -> None:
        result = account(
            k=16,
            integer_shift=2,
            dimension=4,
            rounds=10,
            target_delta=1e-5,
            grid_step=0.002,
            numerical_guard=1e-10,
        )
        self.assertTrue(result.finite_epsilon_available)
        self.assertIsNotNone(result.epsilon_upper)
        self.assertLessEqual(result.total_delta_upper, result.target_delta * (1 + 1e-9))

    def test_target_below_support_floor_is_rejected(self) -> None:
        profile = ComposedPrivacyProfile(k=4, shift=2, compositions=40)
        self.assertIsNone(profile.epsilon_for_delta(profile.infinity_mass / 2))


if __name__ == "__main__":
    unittest.main()
