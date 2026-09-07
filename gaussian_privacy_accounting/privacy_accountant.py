"""Closed-form RDP accounting for the full-participation Gaussian mechanism.

This module intentionally models the mechanism that the repository actually uses:
one clipped client update is released per client per round, with no client
subsampling amplification. It does not model record-level DP-SGD.
"""
from __future__ import annotations

import math


ADJACENCY_SENSITIVITY = {
    "add_remove": 1.0,
    "replace_one": 2.0,
}


def _validate(*, noise_multiplier: float, steps: int, delta: float, adjacency: str) -> None:
    if noise_multiplier <= 0:
        raise ValueError("noise_multiplier must be positive")
    if steps <= 0:
        raise ValueError("steps must be positive")
    if not 0 < delta < 1:
        raise ValueError("delta must lie strictly between 0 and 1")
    if adjacency not in ADJACENCY_SENSITIVITY:
        raise ValueError(f"unknown adjacency: {adjacency}")


def effective_noise_multiplier(raw_noise_multiplier: float, adjacency: str) -> float:
    """Normalize noise by the L2 sensitivity for the selected adjacency.

    A clipped update has norm at most C. Add/remove adjacency therefore has
    sensitivity C, while replace-one adjacency has the conservative bound 2C.
    The repository adds noise with standard deviation raw_noise_multiplier * C.
    """
    if adjacency not in ADJACENCY_SENSITIVITY:
        raise ValueError(f"unknown adjacency: {adjacency}")
    if raw_noise_multiplier <= 0:
        raise ValueError("raw_noise_multiplier must be positive")
    return raw_noise_multiplier / ADJACENCY_SENSITIVITY[adjacency]


def rdp_at_order(
    *,
    raw_noise_multiplier: float,
    steps: int,
    order: float,
    adjacency: str = "replace_one",
) -> float:
    """Return composed Gaussian RDP at order alpha for full participation."""
    if order <= 1:
        raise ValueError("RDP order must be greater than 1")
    sigma = effective_noise_multiplier(raw_noise_multiplier, adjacency)
    return steps * order / (2.0 * sigma * sigma)


def gaussian_rdp_epsilon(
    *,
    raw_noise_multiplier: float,
    steps: int,
    delta: float,
    adjacency: str = "replace_one",
) -> tuple[float, float]:
    """Convert composed Gaussian RDP to a conservative (epsilon, delta) bound.

    For q=1, the Gaussian mechanism is (alpha, alpha/(2*sigma^2))-RDP.
    RDP composes additively across ``steps``. Using the classic conversion
    epsilon = RDP(alpha) + log(1/delta)/(alpha-1), the continuous optimum has
    a closed form, returned together with its optimal order.
    """
    _validate(
        noise_multiplier=raw_noise_multiplier,
        steps=steps,
        delta=delta,
        adjacency=adjacency,
    )
    sigma = effective_noise_multiplier(raw_noise_multiplier, adjacency)
    coefficient = steps / (2.0 * sigma * sigma)
    log_inverse_delta = math.log(1.0 / delta)
    best_alpha = 1.0 + math.sqrt(log_inverse_delta / coefficient)
    epsilon = coefficient + 2.0 * math.sqrt(coefficient * log_inverse_delta)
    return epsilon, best_alpha


def required_raw_noise_multiplier(
    *,
    target_epsilon: float,
    steps: int,
    delta: float,
    adjacency: str = "replace_one",
) -> float:
    """Invert the closed-form bound to obtain a raw noise multiplier."""
    if target_epsilon <= 0:
        raise ValueError("target_epsilon must be positive")
    _validate(noise_multiplier=1.0, steps=steps, delta=delta, adjacency=adjacency)
    log_inverse_delta = math.log(1.0 / delta)
    sqrt_coefficient = math.sqrt(log_inverse_delta + target_epsilon) - math.sqrt(
        log_inverse_delta
    )
    coefficient = sqrt_coefficient * sqrt_coefficient
    effective_sigma = math.sqrt(steps / (2.0 * coefficient))
    return effective_sigma * ADJACENCY_SENSITIVITY[adjacency]


def public_deterministic_seed_epsilon() -> float:
    """Return infinity when the verifier can reconstruct and subtract noise."""
    return math.inf
