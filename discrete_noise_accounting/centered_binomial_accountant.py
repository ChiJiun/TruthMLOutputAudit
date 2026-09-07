"""Conservative PLD accountant for the exact centered-binomial circuit sampler.

The scalar mechanism releases f(D) + (Binomial(2k, 1/2) - k) * unit.
For a fixed integer shift, the code constructs the exact scalar privacy-loss
distribution. Composition rounds every finite privacy loss upward to a public
grid before FFT convolution, and adds an explicit floating-point guard.

The finite support creates a non-zero delta floor.  The accountant rejects a
target delta below that floor instead of returning a misleading finite epsilon.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.signal import fftconvolve


@dataclass(frozen=True)
class PrivacyResult:
    k: int
    integer_shift: int
    compositions: int
    target_delta: float
    epsilon_upper: float | None
    delta_at_epsilon: float | None
    unavoidable_delta_floor: float
    finite_mass: float
    grid_step: float
    numerical_guard: float
    field_sampler_bias_delta: float
    total_delta_upper: float | None
    finite_epsilon_available: bool


def centered_binomial_pmf(k: int) -> dict[int, float]:
    if k <= 0:
        raise ValueError("k must be positive")
    denominator = float(1 << (2 * k))
    return {
        value - k: math.comb(2 * k, value) / denominator
        for value in range(2 * k + 1)
    }


def scalar_hockey_stick_delta(k: int, shift: int, epsilon: float) -> float:
    """Exact scalar hockey-stick divergence, maximized over both orientations."""
    pmf = centered_binomial_pmf(k)

    def directed(direction: int) -> float:
        return sum(
            max(probability - math.exp(epsilon) * pmf.get(value - direction, 0.0), 0.0)
            for value, probability in pmf.items()
        )

    magnitude = abs(int(shift))
    return max(directed(magnitude), directed(-magnitude))


def scalar_pld(k: int, shift: int) -> tuple[list[tuple[float, float]], float]:
    """Return finite (privacy loss, P-mass) pairs and the infinite-loss mass."""
    pmf = centered_binomial_pmf(k)
    direction = abs(int(shift))
    if direction == 0:
        return [(0.0, 1.0)], 0.0
    finite: list[tuple[float, float]] = []
    infinity_mass = 0.0
    for value, probability in pmf.items():
        neighbor = pmf.get(value - direction, 0.0)
        if neighbor == 0.0:
            infinity_mass += probability
        else:
            loss = math.nextafter(math.log(probability / neighbor), math.inf)
            finite.append((loss, probability))
    return finite, infinity_mass


def _convolve_power(base: np.ndarray, base_offset: int, exponent: int) -> tuple[np.ndarray, int]:
    result = np.array([1.0], dtype=np.float64)
    result_offset = 0
    factor = base.astype(np.float64, copy=True)
    factor_offset = base_offset
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = fftconvolve(result, factor)
            result_offset += factor_offset
            result[result < 0.0] = 0.0
        remaining >>= 1
        if remaining:
            factor = fftconvolve(factor, factor)
            factor_offset *= 2
            factor[factor < 0.0] = 0.0
    return result, result_offset


class ComposedPrivacyProfile:
    def __init__(
        self,
        *,
        k: int,
        shift: int,
        compositions: int,
        grid_step: float = 0.002,
        numerical_guard: float = 1e-10,
    ) -> None:
        if compositions <= 0:
            raise ValueError("compositions must be positive")
        if grid_step <= 0 or numerical_guard <= 0:
            raise ValueError("grid_step and numerical_guard must be positive")
        finite, scalar_infinity = scalar_pld(k, shift)
        bins: dict[int, float] = {}
        for loss, probability in finite:
            bin_index = math.ceil(loss / grid_step)
            bins[bin_index] = bins.get(bin_index, 0.0) + probability
        minimum = min(bins)
        maximum = max(bins)
        base = np.zeros(maximum - minimum + 1, dtype=np.float64)
        for index, probability in bins.items():
            base[index - minimum] += probability
        composed, offset = _convolve_power(base, minimum, compositions)
        composed_log_finite_mass = compositions * math.log1p(-scalar_infinity)
        expected_finite_mass = math.exp(composed_log_finite_mass)
        composed_infinity_mass = -math.expm1(composed_log_finite_mass)
        observed_mass = float(composed.sum())
        mass_error = abs(observed_mass - expected_finite_mass)
        if observed_mass > 0:
            composed *= expected_finite_mass / observed_mass
        self.k = k
        self.shift = abs(int(shift))
        self.compositions = compositions
        self.grid_step = grid_step
        self.loss_probabilities = composed
        self.offset = offset
        self.finite_mass = expected_finite_mass
        self.infinity_mass = composed_infinity_mass
        self.numerical_guard = numerical_guard + mass_error

    def delta_upper(self, epsilon: float) -> float:
        indices = np.arange(self.loss_probabilities.size, dtype=np.float64) + self.offset
        rounded_losses = indices * self.grid_step
        positive = rounded_losses > epsilon
        finite_delta = float(
            np.sum(
                self.loss_probabilities[positive]
                * (1.0 - np.exp(epsilon - rounded_losses[positive]))
            )
        )
        return min(1.0, self.infinity_mass + finite_delta + self.numerical_guard)

    def epsilon_for_delta(self, target_delta: float) -> float | None:
        if not 0 < target_delta < 1:
            raise ValueError("target_delta must be in (0, 1)")
        if target_delta <= self.infinity_mass + self.numerical_guard:
            return None
        low = 0.0
        high = 1.0
        while self.delta_upper(high) > target_delta and high < 4096.0:
            high *= 2.0
        if high >= 4096.0 and self.delta_upper(high) > target_delta:
            return None
        for _ in range(80):
            midpoint = (low + high) / 2.0
            if self.delta_upper(midpoint) > target_delta:
                low = midpoint
            else:
                high = midpoint
        return high


def field_low_bit_bias_bound(*, bits_per_output: int, outputs: int) -> float:
    """Safe TV-distance union bound for low bits of uniform Pasta field elements."""
    modulus_text = "40000000000000000000000000000000224698fc094cf91b992d30ed00000001"
    modulus = int(modulus_text, 16)
    return outputs * (2**bits_per_output) / modulus


def account(
    *,
    k: int,
    integer_shift: int,
    dimension: int,
    rounds: int,
    target_delta: float,
    grid_step: float,
    numerical_guard: float,
) -> PrivacyResult:
    compositions = dimension * rounds
    profile = ComposedPrivacyProfile(
        k=k,
        shift=integer_shift,
        compositions=compositions,
        grid_step=grid_step,
        numerical_guard=numerical_guard,
    )
    field_bias = field_low_bit_bias_bound(bits_per_output=2 * k, outputs=compositions)
    accountant_delta = target_delta - field_bias
    epsilon = profile.epsilon_for_delta(accountant_delta) if accountant_delta > 0 else None
    delta_at_epsilon = profile.delta_upper(epsilon) if epsilon is not None else None
    total_delta = delta_at_epsilon + field_bias if delta_at_epsilon is not None else None
    return PrivacyResult(
        k=k,
        integer_shift=integer_shift,
        compositions=compositions,
        target_delta=target_delta,
        epsilon_upper=epsilon,
        delta_at_epsilon=delta_at_epsilon,
        unavoidable_delta_floor=profile.infinity_mass,
        finite_mass=profile.finite_mass,
        grid_step=grid_step,
        numerical_guard=profile.numerical_guard,
        field_sampler_bias_delta=field_bias,
        total_delta_upper=total_delta,
        finite_epsilon_available=epsilon is not None,
    )


def write_results(results: Iterable[PrivacyResult], output_dir: Path) -> None:
    rows = [asdict(result) for result in results]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "accounting_results.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (output_dir / "accounting_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    primary = rows[0]
    summary = [
        "# discrete-noise accounting Exact Centered-Binomial Privacy Accounting",
        "",
        "## Primary circuit profile",
        "",
        f"- k={primary['k']}, replace-one coordinate shift={primary['integer_shift']}.",
        f"- Compositions={primary['compositions']} (dimension x rounds).",
        f"- Target delta={primary['target_delta']:.3g}.",
        f"- Conservative epsilon upper={primary['epsilon_upper']:.6f}.",
        f"- Accounted total delta upper={primary['total_delta_upper']:.12g}.",
        f"- Finite-support unavoidable delta floor={primary['unavoidable_delta_floor']:.12g}.",
        f"- Field low-bit statistical-distance bound={primary['field_sampler_bias_delta']:.3e}.",
        "",
        "The result is information-theoretic for ideal independent uniform sampler bits. The",
        "actual Poseidon construction gives computational DP under an explicit PRF assumption,",
        "with the PRF distinguishing advantage added to delta. Unique contexts are mandatory.",
        "",
        "The accountant is for the exact finite centered-binomial support; it does not reuse a",
        "Gaussian RDP formula. Privacy-loss values are rounded upward before convolution and the",
        "reported delta includes the declared numerical guard.",
    ]
    (output_dir / "summary.md").write_text("\n".join(summary), encoding="utf-8")


def default_scenarios() -> list[PrivacyResult]:
    scenarios = []
    for k, rounds in [(16, 10), (32, 10), (64, 10), (32, 50)]:
        scenarios.append(
            account(
                k=k,
                integer_shift=2,
                dimension=4,
                rounds=rounds,
                target_delta=1e-5,
                grid_step=0.002,
                numerical_guard=1e-10,
            )
        )
    return scenarios


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "results")
    args = parser.parse_args()
    results = default_scenarios()
    write_results(results, args.output_dir)
    primary = results[0]
    print(
        f"k={primary.k} compositions={primary.compositions} "
        f"epsilon<={primary.epsilon_upper:.6f} delta<={primary.total_delta_upper:.3g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
