import unittest

import torch

from run_robust_aggregation import aggregate_states


class RobustAggregationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.states = [
            {"x": torch.tensor([0.0, 1.0])},
            {"x": torch.tensor([0.1, 1.1])},
            {"x": torch.tensor([-0.1, 0.9])},
            {"x": torch.tensor([0.2, 1.2])},
            {"x": torch.tensor([100.0, -100.0])},
        ]

    def test_mean_is_affected_by_outlier(self) -> None:
        result = aggregate_states(self.states, "mean", trim_count=1)
        self.assertGreater(float(result["x"][0]), 10.0)

    def test_coordinate_median_rejects_outlier(self) -> None:
        result = aggregate_states(self.states, "coordinate_median", trim_count=1)
        torch.testing.assert_close(result["x"], torch.tensor([0.1, 1.0]))

    def test_trimmed_mean_rejects_extremes(self) -> None:
        result = aggregate_states(self.states, "trimmed_mean", trim_count=1)
        torch.testing.assert_close(result["x"], torch.tensor([0.1, 1.0]))

    def test_invalid_trim_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            aggregate_states(self.states[:2], "trimmed_mean", trim_count=1)


if __name__ == "__main__":
    unittest.main()
