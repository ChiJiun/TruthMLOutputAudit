//! Four-parameter synthetic logistic FL with a real proof for every update.
//! Training and dataset provenance remain outside the circuit.
use super::*;
use rand::{rngs::StdRng, Rng, SeedableRng};
use serde::Deserialize;
use std::{collections::HashSet, path::Path};

const UNIT: f64 = 0.1;
type Model = [f64; DIMENSION];
type Sample = (Model, f64);

#[derive(Clone)]
struct Ticket {
    expected: Vec<Fp>,
    consumed: bool,
}

impl Ticket {
    // Every submitted attempt consumes the ticket, even a malformed proof.
    fn submit(&mut self, instances: &[Fp], proof_ok: bool) -> &'static str {
        if self.consumed {
            return "replay_rejected";
        }
        self.consumed = true;
        if instances.len() != INSTANCE_Q_NOISY_START + DIMENSION
            || instances[..INSTANCE_Q_NOISY_START] != self.expected[..]
        {
            return "context_rejected";
        }
        if !proof_ok {
            return "proof_rejected";
        }
        "accepted"
    }
}

fn dataset(seed: u64, client: usize, count: usize) -> Vec<Sample> {
    let mut rng = StdRng::seed_from_u64(seed.wrapping_add((client as u64 + 1) * 100003));
    (0..count)
        .map(|_| {
            let shift = (client as f64 % 3.0 - 1.0) * 0.35;
            let x = [
                rng.gen_range(-1.0..1.0) + shift,
                rng.gen_range(-1.0..1.0),
                rng.gen_range(-1.0..1.0),
                1.0,
            ];
            let y = f64::from(x[0] - 0.8 * x[1] + 0.5 * x[2] > 0.0);
            (x, y)
        })
        .collect()
}

fn local_update(model: Model, samples: &[Sample]) -> [i64; DIMENSION] {
    let mut local = model;
    for _ in 0..2 {
        let mut gradient = [0.0; DIMENSION];
        for (x, y) in samples {
            let logit: f64 = local.iter().zip(x).map(|(w, x)| w * x).sum();
            let error = 1.0 / (1.0 + (-logit.clamp(-30.0, 30.0)).exp()) - y;
            for i in 0..DIMENSION {
                gradient[i] += error * x[i];
            }
        }
        for i in 0..DIMENSION {
            local[i] -= 0.5 * gradient[i] / samples.len() as f64;
        }
    }
    std::array::from_fn(|i| ((local[i] - model[i]) / UNIT).round().clamp(-1.0, 1.0) as i64)
}

fn accuracy(model: Model, samples: &[Sample]) -> f64 {
    samples
        .iter()
        .filter(|(x, y)| {
            let score: f64 = model.iter().zip(x).map(|(w, x)| w * x).sum();
            f64::from(score > 0.0) == *y
        })
        .count() as f64
        / samples.len() as f64
}

fn aggregate(model: Model, updates: &[[i64; DIMENSION]]) -> Model {
    assert!(!updates.is_empty());
    std::array::from_fn(|i| {
        model[i] + UNIT * updates.iter().map(|q| q[i]).sum::<i64>() as f64 / updates.len() as f64
    })
}

fn model_field(model: Model) -> Fp {
    // Canonical f64 bit encoding and full SHA-256 reduced into Fp, domain separated.
    let mut digest = Sha256::new();
    digest.update(b"truthml-four-parameter-model-v1");
    for value in model {
        digest.update(value.to_bits().to_le_bytes());
    }
    digest.finalize().iter().fold(Fp::ZERO, |acc, byte| {
        acc * Fp::from(256) + Fp::from(*byte as u64)
    })
}

fn verify(
    params: &Params<EqAffine>,
    vk: &plonk::VerifyingKey<EqAffine>,
    instances: &[Fp],
    bytes: &[u8],
) -> bool {
    let mut reader = Blake2bRead::<_, EqAffine, Challenge255<_>>::init(bytes);
    plonk::verify_proof(
        params,
        vk,
        SingleVerifier::new(params),
        &[&[instances]],
        &mut reader,
    )
    .is_ok()
}

fn digest_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

#[derive(Serialize, Deserialize)]
struct UpdateRecord {
    client: usize,
    round: usize,
    q_noisy: [i64; DIMENSION],
    public_instances_le_hex: Vec<String>,
    proof_file: String,
    proof_sha256: String,
    proof_bytes: usize,
    prove_seconds: f64,
    verify_seconds: f64,
    gate: String,
}

#[derive(Serialize, Deserialize)]
struct Probe {
    client: usize,
    round: usize,
    attack: String,
    cryptographic_verified: bool,
    gate: String,
}

#[derive(Serialize, Deserialize)]
struct RoundRecord {
    round: usize,
    model_before: Model,
    model_after: Model,
    accepted_clients: usize,
    proof_gated_accuracy: f64,
    quantized_no_noise_accuracy: f64,
    same_noisy_updates_without_gate_max_abs_difference: f64,
    round_wall_seconds_including_probes: f64,
}

#[derive(Serialize, Deserialize)]
struct RunReport {
    schema: String,
    seed: u64,
    clients: usize,
    rounds: usize,
    dimension: usize,
    binomial_k: usize,
    quantization_unit: f64,
    training_samples_per_client: usize,
    test_samples: usize,
    dataset: String,
    secret_source: String,
    keygen_seconds: f64,
    total_wall_seconds: f64,
    training_seconds: f64,
    probe_seconds: f64,
    setup_commitments: Vec<String>,
    updates: Vec<UpdateRecord>,
    probes: Vec<Probe>,
    trajectory: Vec<RoundRecord>,
    claim_scope: String,
}

pub(super) fn run(args: &[String]) {
    assert_eq!(args.len(), 4, "--federated OUTPUT_DIR SEED CLIENTS ROUNDS");
    let output = PathBuf::from(&args[0]);
    // Do not silently mix a partial old run with a new set of OS-random secrets.
    fs::create_dir(&output).expect("output directory must be new (parent must exist)");
    fs::create_dir(output.join("proofs")).unwrap();
    let seed: u64 = args[1].parse().expect("seed");
    let clients: usize = args[2].parse().expect("clients");
    let rounds: usize = args[3].parse().expect("rounds");
    assert!((2..=50).contains(&clients) && (1..=50).contains(&rounds));
    let start = Instant::now();
    let data: Vec<_> = (0..clients).map(|c| dataset(seed, c, 64)).collect();
    let test = dataset(seed.wrapping_add(900_001), 1, 512);
    let secrets: Vec<Fp> = (0..clients).map(|_| Fp::random(OsRng)).collect();
    let commitments: Vec<Fp> = secrets
        .iter()
        .enumerate()
        .map(|(c, secret)| {
            native_hash2(
                native_hash2(Fp::from(TAG_SECRET), Fp::from(c as u64)),
                *secret,
            )
        })
        .collect();
    let params: Params<EqAffine> = Params::new(CIRCUIT_K);
    let empty = demo_bundle(0).circuit.without_witnesses();
    let keygen = Instant::now();
    let vk = plonk::keygen_vk(&params, &empty).expect("vk");
    let pk = plonk::keygen_pk(&params, vk, &empty).expect("pk");
    let keygen_seconds = keygen.elapsed().as_secs_f64();
    let mut report = RunReport {
        schema: "truthml-actual-multiround-v1".into(), seed, clients, rounds,
        dimension: DIMENSION, binomial_k: BINOMIAL_K, quantization_unit: UNIT,
        training_samples_per_client: 64, test_samples: test.len(),
        dataset: "public seeded synthetic binary data; 3 features plus bias; client feature shift".into(),
        secret_source: "OS CSPRNG; fixed secret per client, fresh salt and challenge per update".into(),
        keygen_seconds, total_wall_seconds: 0.0, training_seconds: 0.0, probe_seconds: 0.0,
        setup_commitments: commitments.iter().map(fp_le_hex).collect(),
        updates: vec![], probes: vec![], trajectory: vec![],
        claim_scope: "real per-update Halo2 proofs and accepted-only synthetic FL; training is outside circuit; probes use isolated tickets; privacy of full timing/commitment transcript is not certified".into(),
    };
    let mut model = [0.0; DIMENSION];
    let mut clean = model;
    let mut contexts = HashSet::new();
    for round in 0..rounds {
        let round_start = Instant::now();
        let before = model;
        let model_hash = model_field(before);
        let train_start = Instant::now();
        let clipped: Vec<_> = data.iter().map(|d| local_update(model, d)).collect();
        let clean_updates: Vec<_> = data.iter().map(|d| local_update(clean, d)).collect();
        clean = aggregate(clean, &clean_updates);
        report.training_seconds += train_start.elapsed().as_secs_f64();
        let mut accepted = vec![];
        let mut all_noisy = vec![];
        for client in 0..clients {
            let salt = Fp::random(OsRng);
            // This commitment is received by the host before challenge generation.
            let committed_update = update_commitment_for(clipped[client], salt);
            let nonce = Fp::from((round * clients + client + 1) as u64);
            let challenge = Fp::random(OsRng);
            let expected = vec![
                Fp::from(client as u64),
                Fp::from(round as u64),
                model_hash,
                nonce,
                challenge,
                commitments[client],
                committed_update,
                Fp::from(CLIP_BOUND_SQ),
            ];
            assert!(contexts.insert(expected.iter().map(fp_le_hex).collect::<Vec<_>>()));
            let ticket = Ticket {
                expected,
                consumed: false,
            };
            let bundle = contextual_bundle(
                clipped[client],
                [
                    Fp::from(client as u64),
                    Fp::from(round as u64),
                    model_hash,
                    nonce,
                ],
                secrets[client],
                salt,
                challenge,
            );
            let prove_start = Instant::now();
            let mut transcript = Blake2bWrite::<_, EqAffine, Challenge255<_>>::init(vec![]);
            plonk::create_proof(
                &params,
                &pk,
                &[bundle.circuit],
                &[&[&bundle.instances]],
                OsRng,
                &mut transcript,
            )
            .expect("create actual proof");
            let bytes = transcript.finalize();
            let prove_seconds = prove_start.elapsed().as_secs_f64();
            let verify_start = Instant::now();
            let ok = verify(&params, pk.get_vk(), &bundle.instances, &bytes);
            let verify_seconds = verify_start.elapsed().as_secs_f64();
            let mut live_ticket = ticket.clone();
            let gate = live_ticket.submit(&bundle.instances, ok);
            assert_eq!(gate, "accepted", "honest update must verify");
            accepted.push(bundle.q_noisy);
            all_noisy.push(bundle.q_noisy);
            let proof_file = format!("proofs/round_{round:02}_client_{client:02}.bin");
            fs::write(output.join(&proof_file), &bytes).unwrap();
            report.updates.push(UpdateRecord {
                client,
                round,
                q_noisy: bundle.q_noisy,
                public_instances_le_hex: bundle.instances.iter().map(fp_le_hex).collect(),
                proof_file,
                proof_sha256: digest_hex(&bytes),
                proof_bytes: bytes.len(),
                prove_seconds,
                verify_seconds,
                gate: gate.into(),
            });
            let probe_start = Instant::now();
            // Replay a genuinely verified proof: crypto accepts, state must reject.
            let replay_ok = verify(&params, pk.get_vk(), &bundle.instances, &bytes);
            let replay_gate = live_ticket.submit(&bundle.instances, replay_ok);
            assert!(replay_ok && replay_gate == "replay_rejected");
            report.probes.push(Probe {
                client,
                round,
                attack: "duplicate_submission".into(),
                cryptographic_verified: replay_ok,
                gate: replay_gate.into(),
            });
            for (name, index) in [
                ("client_swap", INSTANCE_CLIENT_ID),
                ("round_swap", INSTANCE_ROUND_ID),
                ("model_swap", INSTANCE_MODEL_HASH),
                ("noisy_update_tamper", INSTANCE_Q_NOISY_START),
            ] {
                let mut changed = bundle.instances.clone();
                changed[index] += Fp::ONE;
                let probe_ok = verify(&params, pk.get_vk(), &changed, &bytes);
                let result = ticket.clone().submit(&changed, probe_ok);
                assert!(!probe_ok && result != "accepted");
                report.probes.push(Probe {
                    client,
                    round,
                    attack: name.into(),
                    cryptographic_verified: probe_ok,
                    gate: result.into(),
                });
            }
            let mut corrupt = bytes.clone();
            corrupt[0] ^= 1;
            let corrupt_ok = verify(&params, pk.get_vk(), &bundle.instances, &corrupt);
            let mut failed_ticket = ticket.clone();
            let failed_gate = failed_ticket.submit(&bundle.instances, corrupt_ok);
            assert!(!corrupt_ok && failed_gate == "proof_rejected");
            report.probes.push(Probe {
                client,
                round,
                attack: "corrupt_proof".into(),
                cryptographic_verified: corrupt_ok,
                gate: failed_gate.into(),
            });
            let retry_gate = failed_ticket.submit(&bundle.instances, ok);
            assert_eq!(retry_gate, "replay_rejected");
            report.probes.push(Probe {
                client,
                round,
                attack: "retry_after_failure".into(),
                cryptographic_verified: ok,
                gate: retry_gate.into(),
            });
            report.probe_seconds += probe_start.elapsed().as_secs_f64();
        }
        model = aggregate(before, &accepted);
        let ungated = aggregate(before, &all_noisy);
        let difference = model
            .iter()
            .zip(ungated)
            .map(|(a, b)| (a - b).abs())
            .fold(0.0_f64, f64::max);
        assert_eq!(difference, 0.0);
        report.trajectory.push(RoundRecord {
            round,
            model_before: before,
            model_after: model,
            accepted_clients: accepted.len(),
            proof_gated_accuracy: accuracy(model, &test),
            quantized_no_noise_accuracy: accuracy(clean, &test),
            same_noisy_updates_without_gate_max_abs_difference: difference,
            round_wall_seconds_including_probes: round_start.elapsed().as_secs_f64(),
        });
        println!(
            "seed={seed} round={round} verified={}/{} accuracy={:.4}",
            accepted.len(),
            clients,
            accuracy(model, &test)
        );
    }
    report.total_wall_seconds = start.elapsed().as_secs_f64();
    fs::write(
        output.join("run.json"),
        serde_json::to_string_pretty(&report).unwrap(),
    )
    .unwrap();
}

fn from_hex(value: &str) -> Fp {
    assert_eq!(value.len(), 64);
    let mut repr = <Fp as PrimeField>::Repr::default();
    for (index, byte) in repr.as_mut().iter_mut().enumerate() {
        *byte = u8::from_str_radix(&value[index * 2..index * 2 + 2], 16).expect("hex byte");
    }
    Option::<Fp>::from(Fp::from_repr(repr)).expect("canonical field element")
}

pub(super) fn verify_saved(path: &Path) {
    let report: RunReport =
        serde_json::from_slice(&fs::read(path).expect("read run")).expect("run json");
    assert_eq!(report.schema, "truthml-actual-multiround-v1");
    assert_eq!(
        (
            report.dimension,
            report.binomial_k,
            report.quantization_unit
        ),
        (DIMENSION, BINOMIAL_K, UNIT)
    );
    assert_eq!(report.updates.len(), report.clients * report.rounds);
    assert_eq!(report.trajectory.len(), report.rounds);
    let params: Params<EqAffine> = Params::new(CIRCUIT_K);
    let vk = plonk::keygen_vk(&params, &demo_bundle(0).circuit.without_witnesses()).unwrap();
    let mut model = [0.0; DIMENSION];
    let mut seen = HashSet::new();
    let mut hashes = HashSet::new();
    for round in 0..report.rounds {
        let mut updates = vec![];
        for client in 0..report.clients {
            let record = &report.updates[round * report.clients + client];
            assert_eq!((record.round, record.client), (round, client));
            let instances: Vec<Fp> = record
                .public_instances_le_hex
                .iter()
                .map(|s| from_hex(s))
                .collect();
            assert_eq!(instances.len(), INSTANCE_Q_NOISY_START + DIMENSION);
            assert_eq!(instances[INSTANCE_CLIENT_ID], Fp::from(client as u64));
            assert_eq!(instances[INSTANCE_ROUND_ID], Fp::from(round as u64));
            assert_eq!(instances[INSTANCE_MODEL_HASH], model_field(model));
            assert_eq!(
                instances[INSTANCE_NONCE],
                Fp::from((round * report.clients + client + 1) as u64)
            );
            assert_eq!(
                instances[INSTANCE_SECRET_COMMITMENT],
                from_hex(&report.setup_commitments[client])
            );
            assert_eq!(instances[INSTANCE_CLIP_BOUND_SQ], Fp::from(CLIP_BOUND_SQ));
            for i in 0..DIMENSION {
                assert_eq!(
                    instances[INSTANCE_Q_NOISY_START + i],
                    fp_from_i64(record.q_noisy[i])
                );
            }
            assert!(seen.insert(record.public_instances_le_hex[..INSTANCE_Q_NOISY_START].to_vec()));
            let relative = Path::new(&record.proof_file);
            assert!(relative
                .components()
                .all(|c| matches!(c, std::path::Component::Normal(_))));
            let bytes = fs::read(path.parent().unwrap().join(relative)).expect("read proof");
            assert_eq!(bytes.len(), record.proof_bytes);
            assert_eq!(digest_hex(&bytes), record.proof_sha256);
            assert!(hashes.insert(record.proof_sha256.clone()));
            assert!(
                verify(&params, &vk, &instances, &bytes),
                "saved proof invalid"
            );
            assert_eq!(record.gate, "accepted");
            updates.push(record.q_noisy);
        }
        let trajectory = &report.trajectory[round];
        assert_eq!(trajectory.round, round);
        assert_eq!(trajectory.model_before, model);
        model = aggregate(model, &updates);
        assert_eq!(trajectory.model_after, model);
        assert_eq!(trajectory.accepted_clients, report.clients);
    }
    println!(
        "verified_from_disk={} rounds={} model_chain_valid=true",
        report.updates.len(),
        report.rounds
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn model_json_roundtrip_preserves_exact_hash_input() {
        let model = [
            -6.938893903907228e-17,
            -0.5333333333333332,
            0.6666666666666667,
            0.3666666666666667,
        ];
        let encoded = serde_json::to_string(&model).unwrap();
        let decoded: Model = serde_json::from_str(&encoded).unwrap();
        assert_eq!(model.map(f64::to_bits), decoded.map(f64::to_bits));
        assert_eq!(model_field(model), model_field(decoded));
    }
    #[test]
    fn failed_attempt_consumes_ticket_and_context_is_checked() {
        let bundle = demo_bundle(42);
        let mut ticket = Ticket {
            expected: bundle.instances[..INSTANCE_Q_NOISY_START].to_vec(),
            consumed: false,
        };
        assert_eq!(ticket.submit(&bundle.instances, false), "proof_rejected");
        assert_eq!(ticket.submit(&bundle.instances, true), "replay_rejected");
        let mut wrong = bundle.instances.clone();
        wrong[INSTANCE_MODEL_HASH] += Fp::ONE;
        ticket.consumed = false;
        assert_eq!(ticket.submit(&wrong, true), "context_rejected");
    }
    #[test]
    fn training_is_data_dependent_and_satisfies_circuit_range() {
        let data = dataset(42, 0, 64);
        let inverted: Vec<_> = data.iter().map(|(x, y)| (*x, 1.0 - y)).collect();
        let update = local_update([0.0; DIMENSION], &data);
        let opposite = local_update([0.0; DIMENSION], &inverted);
        assert_ne!(update, [0; DIMENSION]);
        assert_eq!(update.map(|v| -v), opposite);
        assert!(update.iter().all(|v| (-1..=1).contains(v)));
        let bundle = contextual_bundle(
            update,
            [
                Fp::from(1),
                Fp::from(2),
                model_field([0.0; DIMENSION]),
                Fp::from(3),
            ],
            Fp::from(4),
            Fp::from(5),
            Fp::from(6),
        );
        MockProver::run(CIRCUIT_K, &bundle.circuit, vec![bundle.instances])
            .unwrap()
            .assert_satisfied();
    }
    #[test]
    fn model_binding_and_accepted_only_aggregation() {
        let before = [0.0; DIMENSION];
        let after = aggregate(before, &[[1, -1, 0, 1], [1, 1, 0, 1]]);
        assert_eq!(after, [0.1, 0.0, 0.0, 0.1]);
        assert_ne!(model_field(before), model_field(after));
        assert_eq!(
            from_hex(&fp_le_hex(&model_field(after))),
            model_field(after)
        );
    }
}
