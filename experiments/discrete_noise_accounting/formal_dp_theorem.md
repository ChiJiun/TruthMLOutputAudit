# Formal privacy statement for the Halo2 verifiable-randomness circuit sampler

## Mechanism and adjacency

For each participating client and round, let the quantized, clipped update be
`f(D) in {-1,0,1}^d`, where `D` denotes that client's entire local dataset.
Two federated inputs are **replacement client-level adjacent** when one client
slot's complete local dataset is replaced while every other client is fixed.
Because the allowed output range of that slot is fixed independently of its
number of records, `|f_i(D)-f_i(D')| <= 2` for every coordinate. This is a
client-level statement; it is not the record-adjacency definition used by
record-level DP-SGD.

The ideal mechanism releases

`M(D)_i = f_i(D) + Z_i`,

where each `Z_i = Binomial(2k, 1/2) - k` is independent. Halo2 verifiable-randomness circuit uses `d=4`
and `k=16`; ten releases produce 40 scalar compositions.

## Scalar privacy profile

Let `p(z)` denote the centered-binomial PMF and let `s=2`. For either directed
adjacency, the exact scalar hockey-stick divergence is

`delta_s(epsilon) = sum_z max(p(z) - exp(epsilon) p(z-s), 0)`.

This identity follows directly from the definition of approximate DP for two
discrete additive distributions. Because the binomial support is finite, terms
with `p(z)>0` and `p(z-s)=0` create an unavoidable positive delta floor. No
finite epsilon exists below that floor.

The centered-binomial PMF is symmetric and log-concave, so the extremal
allowed coordinate displacement is `|s|=2`; the two orientations have the
same privacy-loss distribution. The regression suite additionally enumerates
the scalar `|s|=1,2` profiles and an exact two-coordinate product distribution
to check the implemented worst-case and composition upper bounds.

## Composition theorem used by the accountant

For independent coordinates and unique-context rounds, privacy losses add. The
accountant constructs the scalar privacy-loss distribution under `p`, assigns
infinite loss to support-mismatch outcomes, rounds every finite loss upward to
a grid, and convolves 40 times. Since

`g_epsilon(L) = max(1 - exp(epsilon-L), 0)`

is monotone increasing in `L`, upward rounding yields an upper bound on delta.
The reported value additionally includes the exact composed infinite-loss mass,
the observed convolution mass error, and a declared numerical guard.

Therefore, if the accountant returns `epsilon_upper` with
`delta_upper <= delta_target`, the ideal 40-release mechanism is
`(epsilon_upper, delta_target)`-DP for the stated replace-one adjacency.

## Field-output sampling correction

The circuit takes the low `2k` bits of a canonical uniform Pasta field element.
For `b=2k`, reduction to the low bits has statistical distance at most `2^b/p`
from uniform `b`-bit strings, where `p` is the field modulus. A union bound over
all outputs is added to the reported delta.

## Real PRG theorem and exact claim boundary

Halo2 verifiable-randomness circuit samples the setup key with the operating-system CSPRNG and replaces
ideal independent field samples by keyed, context-separated Poseidon
evaluations. The public experiment seed never derives this key. Under the
assumption that this construction is a secure
PRF for unique inputs, the real mechanism is computational
`(epsilon_upper, delta_target + Adv_PRF)`-DP against probabilistic polynomial-
time verifiers. `Adv_PRF` is the verifier's distinguishing advantage.

This is a conditional computational-DP theorem, not an unconditional proof of
Poseidon PRF security. Reusing a context, allowing post-challenge secret
selection, or revealing the secret/noise invalidates the theorem. The context-bound randomness protocol
commit-before-challenge state machine and setup-time immutable commitment are
therefore mandatory parts of the mechanism.

The theorem protects replacement of one participating client's entire local
dataset for the explicitly constrained release and fixed participation
schedule. It does not hide participation, prove record-level DP-SGD,
full-training correctness, privacy against selective abort, or robustness to a
poisoned but in-range update. Add/remove client adjacency would require a
separate null-client encoding and accountant.
