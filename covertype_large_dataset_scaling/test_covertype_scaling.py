import unittest

import numpy as np

from covertype_large_dataset_scaling.run_covertype_scaling import (
    MulticlassLinearModel,
    stratified_client_indices,
    stratified_subsample,
    summarize,
)


class CoverTypeScalingTests(unittest.TestCase):
    def test_linear_model_has_expected_update_dimension(self) -> None:
        model = MulticlassLinearModel(input_dim=54, num_classes=7)
        self.assertEqual(sum(parameter.numel() for parameter in model.parameters()), 385)

    def test_stratified_subsample_is_deterministic_and_sized(self) -> None:
        labels = np.repeat(np.arange(4), 50)
        indices = np.arange(len(labels))
        first = stratified_subsample(indices, labels, size=80, seed=42)
        second = stratified_subsample(indices, labels, size=80, seed=42)
        self.assertTrue(np.array_equal(first, second))
        self.assertEqual(len(first), 80)
        self.assertEqual(set(labels[first]), {0, 1, 2, 3})

    def test_client_partition_covers_each_example_once(self) -> None:
        labels = np.repeat(np.arange(3), 31)
        groups = stratified_client_indices(labels, clients=3, seed=42)
        combined = np.concatenate(groups)
        self.assertEqual(len(combined), len(labels))
        self.assertEqual(len(np.unique(combined)), len(labels))
        self.assertLessEqual(max(map(len, groups)) - min(map(len, groups)), 3)

    def test_summary_computes_paired_retention(self) -> None:
        rows = []
        for seed, fl, dp in [(42, 0.8, 0.72), (52, 0.82, 0.74)]:
            common = {
                "dataset": "covertype", "seed": seed, "train_size": 100,
                "test_size": 20, "input_dim": 54, "num_classes": 7,
                "parameter_count": 385, "training_sec": 1.0, "wall_sec": 2.0,
                "peak_rss_mib": 500.0, "training_samples_per_sec": 100.0,
            }
            rows.append({**common, "mode": "fl", "final_accuracy": fl})
            rows.append({**common, "mode": "dp", "final_accuracy": dp})
        result = summarize(rows)[0]
        self.assertAlmostEqual(result["fl_final_mean"], 0.81)
        self.assertAlmostEqual(result["dp_final_mean"], 0.73)
        self.assertAlmostEqual(result["dp_fl_retention"], 0.73 / 0.81, places=6)


if __name__ == "__main__":
    unittest.main()
