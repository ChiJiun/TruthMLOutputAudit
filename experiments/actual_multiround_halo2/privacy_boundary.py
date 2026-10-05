"""Sampler-only budget diagnostics; no claim about a complete ZK transcript.

Uses exact rational support-mismatch probabilities and Decimal scalar evaluation.
Basic composition is intentionally conservative and avoids transferring the
existing fixed-displacement FFT calculation to adaptive training without review.
"""
from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path


def pmf(k):
    return {j-k: Fraction(math.comb(2*k,j), 2**(2*k)) for j in range(2*k+1)}


def scalar_floor(k, shift=2):
    distribution = pmf(k)
    return sum((p for z,p in distribution.items() if z-shift not in distribution), Fraction(0))


def scalar_epsilon(k, target_delta):
    # Higher precision than the original FFT accountant, but not interval arithmetic.
    with localcontext() as context:
        context.prec = 70
        distribution = {z: Decimal(p.numerator)/Decimal(p.denominator) for z,p in pmf(k).items()}
        target = Decimal(str(target_delta)) - Decimal('1e-50')
        floor = scalar_floor(k)
        if target <= Decimal(floor.numerator)/Decimal(floor.denominator):
            return None
        def delta(epsilon):
            factor = epsilon.exp()
            return max(sum((max(p-factor*distribution.get(z-shift, Decimal(0)), Decimal(0))
                            for z,p in distribution.items()), Decimal(0)) for shift in (1,2))
        low, high = Decimal(0), Decimal(100)
        for _ in range(180):
            midpoint = (low+high)/2
            if delta(midpoint) > target:
                low = midpoint
            else:
                high = midpoint
        return high + Decimal('1e-40')


def scenario(dimension, rounds, k, delta=1e-5):
    n = dimension*rounds
    single = scalar_floor(k)
    # Exact rational expression for N independent, maximal-displacement releases.
    floor = 1-(1-single)**n
    with localcontext() as context:
        context.prec = 70
        per_release = Decimal(str(delta))/n
        epsilon = scalar_epsilon(k, per_release)
        total = float(epsilon*n) if epsilon is not None else None
    return {"dimension": dimension,"rounds":rounds,"k":k,"scalar_releases":n,
            "target_delta":delta,"support_floor":float(floor),
            "below_support_floor":float(floor)>=delta,
            "basic_composition_epsilon":total,
            "scope":"ideal independent binomial bits; coordinatewise +/-1 update envelope; not full transcript or production-model theorem"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir",type=Path,default=Path(__file__).parent/'privacy_results')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    rows = [scenario(d,r,k) for d,r,k in [(4,3,16),(4,10,16),(4,20,16),(4,10,32),(4,10,64),(385,20,16),(1991,20,16)]]
    (args.output_dir/'boundary.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))


if __name__ == '__main__':
    main()
