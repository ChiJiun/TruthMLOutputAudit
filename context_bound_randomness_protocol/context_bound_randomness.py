"""Reference semantics for a context-bound hidden-randomness VDP update.

This module is deliberately a host-side reference implementation, not a ZK
proof system.  It fixes the public statement and private witness that a later
circuit must implement exactly.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any


DOMAIN = "vdp-fl-context-randomness-v1"


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def tagged_hash(tag: str, *parts: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(DOMAIN.encode("ascii"))
    digest.update(b"\x00")
    digest.update(tag.encode("ascii"))
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def secret_commitment(client_secret: bytes) -> str:
    return tagged_hash("client-secret", client_secret)


def update_commitment(q_clipped: list[int], salt: bytes) -> str:
    return tagged_hash("clipped-update", salt, canonical_json(q_clipped))


def context_message(statement: dict[str, Any]) -> bytes:
    fields = {
        "protocol": statement["protocol"],
        "client_id": statement["client_id"],
        "round_id": statement["round_id"],
        "model_hash": statement["model_hash"],
        "nonce": statement["nonce"],
        "update_commitment": statement["update_commitment"],
        "server_challenge": statement["server_challenge"],
        "noise_k": statement["noise_k"],
        "noise_unit": statement["noise_unit"],
        "dimension": statement["dimension"],
    }
    return canonical_json(fields)


def derive_hidden_seed(client_secret: bytes, statement: dict[str, Any]) -> bytes:
    """Derive a seed hidden from a verifier that knows only the statement."""
    return hmac.new(client_secret, context_message(statement), hashlib.sha256).digest()


def centered_binomial_noise(
    seed: bytes, *, dimension: int, k: int, noise_unit: int
) -> list[int]:
    """Deterministic integer centered-binomial sampler used as a reference.

    A circuit implementation must replace SHAKE/HMAC with explicitly selected
    circuit-friendly primitives and re-establish the DP analysis for the exact
    sampler.  This host implementation defines behavior; it does not establish
    a finite privacy budget by itself.
    """
    if dimension <= 0 or k <= 0 or noise_unit <= 0:
        raise ValueError("dimension, k, and noise_unit must be positive")
    bit_count = dimension * 2 * k
    stream = hashlib.shake_256(DOMAIN.encode("ascii") + b"\x00noise\x00" + seed).digest(
        (bit_count + 7) // 8
    )
    bits = [(byte >> offset) & 1 for byte in stream for offset in range(8)]
    output: list[int] = []
    cursor = 0
    for _ in range(dimension):
        positive = sum(bits[cursor : cursor + k])
        cursor += k
        negative = sum(bits[cursor : cursor + k])
        cursor += k
        output.append((positive - negative) * noise_unit)
    return output


def add_vectors(left: list[int], right: list[int]) -> list[int]:
    if len(left) != len(right):
        raise ValueError("Vector dimensions differ")
    return [a + b for a, b in zip(left, right)]


def squared_norm(vector: list[int]) -> int:
    return sum(value * value for value in vector)


@dataclass
class PendingUpdate:
    commitment_id: str
    client_id: int
    round_id: int
    model_hash: str
    nonce: str
    update_commitment: str
    challenge_id: str | None = None


@dataclass
class ChallengeRecord:
    challenge_id: str
    commitment_id: str
    challenge: bytes
    consumed: bool = False


class ReferenceCoordinator:
    """Reference state machine enforcing commit-before-challenge and freshness."""

    def __init__(self) -> None:
        self.client_commitments: dict[int, str] = {}
        self.pending: dict[str, PendingUpdate] = {}
        self.challenges: dict[str, ChallengeRecord] = {}
        self.seen_proofs: set[str] = set()

    def register_client(self, client_id: int, commitment: str) -> None:
        if client_id in self.client_commitments:
            raise ValueError("Client randomness commitment is already registered")
        self.client_commitments[client_id] = commitment

    def commit_update(
        self,
        *,
        client_id: int,
        round_id: int,
        model_hash: str,
        nonce: str,
        commitment: str,
    ) -> str:
        if client_id not in self.client_commitments:
            raise ValueError("Client must register randomness before committing an update")
        record_fields = {
            "client_id": client_id,
            "round_id": round_id,
            "model_hash": model_hash,
            "nonce": nonce,
            "update_commitment": commitment,
        }
        commitment_id = tagged_hash("pending-update", canonical_json(record_fields))
        if commitment_id in self.pending:
            raise ValueError("Duplicate update commitment")
        self.pending[commitment_id] = PendingUpdate(
            commitment_id=commitment_id,
            client_id=client_id,
            round_id=round_id,
            model_hash=model_hash,
            nonce=nonce,
            update_commitment=commitment,
        )
        return commitment_id

    def issue_challenge(self, commitment_id: str, challenge: bytes) -> str:
        if len(challenge) < 16:
            raise ValueError("Server challenge must contain at least 128 bits")
        pending = self.pending[commitment_id]
        if pending.challenge_id is not None:
            raise ValueError("Only one server challenge may be issued per update commitment")
        challenge_id = tagged_hash(
            "server-challenge", commitment_id.encode("ascii"), challenge
        )
        pending.challenge_id = challenge_id
        self.challenges[challenge_id] = ChallengeRecord(
            challenge_id=challenge_id,
            commitment_id=commitment_id,
            challenge=challenge,
        )
        return challenge_id

    def build_statement(
        self,
        *,
        commitment_id: str,
        q_noisy: list[int],
        clip_bound_sq: int,
        noise_k: int,
        noise_unit: int,
    ) -> dict[str, Any]:
        pending = self.pending[commitment_id]
        if pending.challenge_id is None:
            raise ValueError("Challenge must be issued after the update commitment")
        challenge = self.challenges[pending.challenge_id]
        return {
            "protocol": DOMAIN,
            "commitment_id": commitment_id,
            "challenge_id": challenge.challenge_id,
            "client_id": pending.client_id,
            "round_id": pending.round_id,
            "model_hash": pending.model_hash,
            "nonce": pending.nonce,
            "client_secret_commitment": self.client_commitments[pending.client_id],
            "update_commitment": pending.update_commitment,
            "server_challenge": challenge.challenge.hex(),
            "clip_bound_sq": clip_bound_sq,
            "noise_k": noise_k,
            "noise_unit": noise_unit,
            "dimension": len(q_noisy),
            "q_noisy": q_noisy,
        }

    def verify_reference(
        self, statement: dict[str, Any], witness: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate the intended circuit relation while exposing the witness.

        A later ZK backend must prove the same checks without revealing witness.
        The challenge is consumed on every verification attempt to prevent
        adaptive retries after a failed proof.
        """
        challenge_id = str(statement.get("challenge_id", ""))
        record = self.challenges.get(challenge_id)
        freshness_ok = record is not None and not record.consumed
        if record is not None:
            record.consumed = True

        pending = self.pending.get(str(statement.get("commitment_id", "")))
        context_ok = bool(
            record is not None
            and pending is not None
            and record.commitment_id == pending.commitment_id
            and challenge_id == pending.challenge_id
            and statement.get("protocol") == DOMAIN
            and int(statement.get("client_id", -1)) == pending.client_id
            and int(statement.get("round_id", -1)) == pending.round_id
            and statement.get("model_hash") == pending.model_hash
            and statement.get("nonce") == pending.nonce
            and statement.get("update_commitment") == pending.update_commitment
            and statement.get("server_challenge") == record.challenge.hex()
        )

        try:
            client_secret = bytes.fromhex(str(witness["client_secret"]))
            update_salt = bytes.fromhex(str(witness["update_salt"]))
            q_clipped = [int(value) for value in witness["q_clipped"]]
            q_noise = [int(value) for value in witness["q_noise"]]
            q_noisy = [int(value) for value in statement["q_noisy"]]
            dimensions_ok = (
                len(q_clipped)
                == len(q_noise)
                == len(q_noisy)
                == int(statement["dimension"])
            )
        except (KeyError, TypeError, ValueError):
            client_secret = b""
            update_salt = b""
            q_clipped = []
            q_noise = []
            q_noisy = []
            dimensions_ok = False

        registered_commitment = self.client_commitments.get(
            int(statement.get("client_id", -1)), ""
        )
        secret_commitment_ok = bool(
            client_secret
            and secret_commitment(client_secret) == registered_commitment
            and statement.get("client_secret_commitment") == registered_commitment
        )
        update_commitment_ok = bool(
            dimensions_ok
            and update_commitment(q_clipped, update_salt)
            == statement.get("update_commitment")
        )
        clip_ok = bool(
            dimensions_ok and squared_norm(q_clipped) <= int(statement.get("clip_bound_sq", -1))
        )

        if context_ok and secret_commitment_ok and dimensions_ok:
            seed = derive_hidden_seed(client_secret, statement)
            expected_noise = centered_binomial_noise(
                seed,
                dimension=int(statement["dimension"]),
                k=int(statement["noise_k"]),
                noise_unit=int(statement["noise_unit"]),
            )
            noise_generation_ok = hmac.compare_digest(
                canonical_json(q_noise), canonical_json(expected_noise)
            )
        else:
            noise_generation_ok = False
        relation_ok = bool(dimensions_ok and add_vectors(q_clipped, q_noise) == q_noisy)
        proof_id = tagged_hash("reference-proof", canonical_json(statement))
        replay_ok = proof_id not in self.seen_proofs
        self.seen_proofs.add(proof_id)
        checks = {
            "freshness_ok": freshness_ok,
            "context_ok": context_ok,
            "dimensions_ok": dimensions_ok,
            "secret_commitment_ok": secret_commitment_ok,
            "update_commitment_ok": update_commitment_ok,
            "clip_ok": clip_ok,
            "noise_generation_ok": noise_generation_ok,
            "relation_ok": relation_ok,
            "replay_ok": replay_ok,
        }
        return {
            "accepted": all(checks.values()),
            "checks": checks,
            "proof_id": proof_id,
            "failed_checks": [name for name, passed in checks.items() if not passed],
        }


def build_honest_bundle(
    *,
    coordinator: ReferenceCoordinator,
    client_id: int,
    round_id: int,
    model_hash: str,
    nonce: str,
    client_secret: bytes,
    update_salt: bytes,
    q_clipped: list[int],
    server_challenge: bytes,
    clip_bound_sq: int,
    noise_k: int,
    noise_unit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    coordinator.register_client(client_id, secret_commitment(client_secret))
    commitment_id = coordinator.commit_update(
        client_id=client_id,
        round_id=round_id,
        model_hash=model_hash,
        nonce=nonce,
        commitment=update_commitment(q_clipped, update_salt),
    )
    coordinator.issue_challenge(commitment_id, server_challenge)
    provisional = coordinator.build_statement(
        commitment_id=commitment_id,
        q_noisy=[0] * len(q_clipped),
        clip_bound_sq=clip_bound_sq,
        noise_k=noise_k,
        noise_unit=noise_unit,
    )
    seed = derive_hidden_seed(client_secret, provisional)
    q_noise = centered_binomial_noise(
        seed, dimension=len(q_clipped), k=noise_k, noise_unit=noise_unit
    )
    statement = coordinator.build_statement(
        commitment_id=commitment_id,
        q_noisy=add_vectors(q_clipped, q_noise),
        clip_bound_sq=clip_bound_sq,
        noise_k=noise_k,
        noise_unit=noise_unit,
    )
    witness = {
        "client_secret": client_secret.hex(),
        "update_salt": update_salt.hex(),
        "q_clipped": q_clipped,
        "q_noise": q_noise,
    }
    return statement, witness
