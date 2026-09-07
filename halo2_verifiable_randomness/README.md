# Halo2 verifiable-randomness circuit — Actual Halo2 Context-Bound Verifiable Randomness

This crate maps the context-bound randomness protocol host reference into a real Zcash Halo2 proof.

The circuit proves, without revealing the client secret, clipped update, salt,
PRG outputs, or noise vector, that:

1. a setup-time Poseidon client-secret commitment opens correctly;
2. the clipped update opens the pre-challenge Poseidon commitment;
3. all public client/round/model/nonce/challenge fields are folded into a
   context hash;
4. Poseidon PRG outputs are canonically decomposed into field bits;
5. the first `2k` bits per coordinate form exact centered-binomial noise;
6. `q_noisy = q_clipped + q_noise` and the integer clipping bound holds.

Freshness, one-challenge-per-commitment, and replay-cache checks remain host
state-machine checks, as specified in context-bound randomness protocol.

Run:

```powershell
cargo test --release
cargo run --release -- results/halo2_context_noise_proof.json
```

The fixed demonstrator profile uses four integer coordinates, squared clipping
bound `4`, and `k=16`; the public bound is constrained to that circuit constant.
This is an actual
IPA Halo2 proof and a second backend alongside EZKL, but it is not a proof of
full local training. The privacy guarantee for the exact centered-binomial
sampler is calculated separately by discrete-noise accounting.

The executable obtains the client secret, commitment salt, and server challenge
from the operating-system CSPRNG. `experiment_seed` only labels the run and
varies a public nonce; it never derives secret material. The result exports the
exact public instance vector but deliberately omits private witnesses and their
hashes (the four-coordinate witness space is too small for a hash to hide it).
