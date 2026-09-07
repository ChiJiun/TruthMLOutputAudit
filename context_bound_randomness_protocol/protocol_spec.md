# Context-Bound Hidden-Randomness VDP-FL Protocol Spec v1

## Research objective

Gaussian privacy accounting showed that a public deterministic seed lets the verifier reconstruct and subtract the noise. multi-round threat matrix showed that proof+clip+relation alone accepts replay and zero-noise submissions. This specification defines the exact public statement, private witness, state transition, and reference checks needed before implementing a new circuit.

The goal is narrower than full local-training correctness: prove that a committed, clipped client update was combined with context-bound noise derived from hidden client randomness and a fresh server challenge.

## Setup assumption

Each client registers one long-lived randomness commitment before training rounds begin. Registration is immutable for the experiment. This prevents a client from choosing a new randomness secret after seeing a particular update or server challenge.

The host reference uses SHA-256 commitments, HMAC-SHA256 derivation and SHAKE256 expansion. These are reference primitives, not a circuit/backend decision. A paper implementation must select circuit-friendly primitives and analyze their assumptions.

## Protocol order

1. Client clips and quantizes its update.
2. Client commits to `q_clipped` with private salt and fixed round/model context.
3. Server issues exactly one fresh challenge for that commitment.
4. Client derives a hidden seed from its registered secret and the full context.
5. Client deterministically samples integer noise and forms `q_noisy`.
6. Client proves the relation below; server consumes the challenge on any attempt.
7. Server rejects reused proof IDs or challenges.

Commit-before-challenge and single-use challenges are required to limit adaptive randomness grinding. Dropout/selective-abort leakage remains a separate formal-analysis obligation.

## Public statement

- protocol/version domain
- commitment ID and update commitment
- client ID, round ID, model hash and nonce
- registered client-secret commitment
- server challenge and challenge ID
- clipping squared bound
- noise sampler parameters and vector dimension
- `q_noisy`

The statement does not include the client secret, derived seed or `q_noise`.

## Private witness

- registered client secret opening
- update-commitment salt
- `q_clipped`
- `q_noise`

## Intended circuit relation

The circuit/proof relation must establish all of the following:

1. The client-secret opening matches the setup-time public commitment.
2. The clipped-update opening matches the pre-challenge update commitment.
3. `sum(q_clipped[i]^2) <= clip_bound_sq`.
4. The hidden seed is derived from client secret, server challenge, client/round/model/nonce and update commitment.
5. `q_noise` is the exact output of the selected integer-noise sampler from that seed.
6. `q_noisy[i] = q_clipped[i] + q_noise[i]` for every coordinate.
7. All public context matches the server's pending commitment/challenge record.

Freshness and replay-cache checks are stateful host checks unless a recursive/stateful proof system is selected.

## Security claims not yet available

- No actual ZK proof is produced by context-bound randomness protocol.
- The centered-binomial reference sampler does not yet have a repository accountant proving a target client-level or record-level `(epsilon, delta)` for the quantized mechanism.
- HMAC/SHAKE reference behavior is not yet mapped to Halo2/EZKL constraints.
- A malicious client can still choose a poisoned `q_clipped` within the bound; local-training provenance remains out of scope.
- Selective abort, collusion, registration/authentication and challenge generation need a formal threat model.

context-bound randomness protocol therefore establishes a testable protocol contract and eliminates the previous specification ambiguity. It is the prerequisite for, not a substitute for, a formal verifiable-randomness circuit.
