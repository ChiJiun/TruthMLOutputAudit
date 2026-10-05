use ff::{Field, PrimeField};
use halo2_gadgets::poseidon::{
    primitives::{self as poseidon, ConstantLength, P128Pow5T3},
    Hash, Pow5Chip, Pow5Config,
};
use halo2_proofs::{
    circuit::{AssignedCell, Layouter, SimpleFloorPlanner, Value},
    dev::MockProver,
    pasta::Fp,
    plonk::{
        self, Advice, Circuit, Column, ConstraintSystem, Error, Fixed, Instance, Selector,
        SingleVerifier,
    },
    poly::{commitment::Params, Rotation},
    transcript::{Blake2bRead, Blake2bWrite, Challenge255},
};
use num_bigint::BigUint;
use pasta_curves::EqAffine;
use rand::rngs::OsRng;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{convert::TryInto, fs, path::PathBuf, time::Instant};

const WIDTH: usize = 3;
const RATE: usize = 2;
const DIMENSION: usize = 4;
const BINOMIAL_K: usize = 16;
const FIELD_BITS: usize = 255;
const CIRCUIT_K: u32 = 13;
const NOISE_UNIT: i64 = 1;
const CLIP_BOUND_SQ: u64 = 4;

const TAG_SECRET: u64 = 30_001;
const TAG_UPDATE: u64 = 30_002;
const TAG_CONTEXT: u64 = 30_003;
const TAG_PRG: u64 = 30_004;

const INSTANCE_CLIENT_ID: usize = 0;
const INSTANCE_ROUND_ID: usize = 1;
const INSTANCE_MODEL_HASH: usize = 2;
const INSTANCE_NONCE: usize = 3;
const INSTANCE_CHALLENGE: usize = 4;
const INSTANCE_SECRET_COMMITMENT: usize = 5;
const INSTANCE_UPDATE_COMMITMENT: usize = 6;
const INSTANCE_CLIP_BOUND_SQ: usize = 7;
const INSTANCE_Q_NOISY_START: usize = 8;

type PoseidonChip = Pow5Chip<Fp, WIDTH, RATE>;

mod federated;

#[derive(Clone, Debug)]
struct CanonicalBitsConfig {
    bit: Column<Advice>,
    accumulator: Column<Advice>,
    equal_prefix: Column<Advice>,
    less_prefix: Column<Advice>,
    power: Column<Fixed>,
    modulus_bit: Column<Fixed>,
    selector: Selector,
}

impl CanonicalBitsConfig {
    fn configure(meta: &mut ConstraintSystem<Fp>) -> Self {
        let bit = meta.advice_column();
        let accumulator = meta.advice_column();
        let equal_prefix = meta.advice_column();
        let less_prefix = meta.advice_column();
        let power = meta.fixed_column();
        let modulus_bit = meta.fixed_column();
        for column in [bit, accumulator, equal_prefix, less_prefix] {
            meta.enable_equality(column);
        }
        let selector = meta.selector();
        meta.create_gate("canonical field decomposition", |meta| {
            let enabled = meta.query_selector(selector);
            let bit_value = meta.query_advice(bit, Rotation::cur());
            let acc = meta.query_advice(accumulator, Rotation::cur());
            let acc_next = meta.query_advice(accumulator, Rotation::next());
            let eq = meta.query_advice(equal_prefix, Rotation::cur());
            let eq_next = meta.query_advice(equal_prefix, Rotation::next());
            let less = meta.query_advice(less_prefix, Rotation::cur());
            let less_next = meta.query_advice(less_prefix, Rotation::next());
            let pow = meta.query_fixed(power);
            let modulus = meta.query_fixed(modulus_bit);
            let one = halo2_proofs::plonk::Expression::Constant(Fp::ONE);
            let matches_modulus = modulus.clone() * bit_value.clone()
                + (one.clone() - modulus.clone()) * (one.clone() - bit_value.clone());
            let becomes_less = eq.clone() * modulus.clone() * (one.clone() - bit_value.clone());
            vec![
                enabled.clone() * bit_value.clone() * (one.clone() - bit_value.clone()),
                enabled.clone() * (acc_next - acc - bit_value.clone() * pow),
                enabled.clone() * (eq_next - eq.clone() * matches_modulus),
                enabled.clone() * (less_next - less - becomes_less),
                enabled * eq * (one - modulus) * bit_value,
            ]
        });
        Self {
            bit,
            accumulator,
            equal_prefix,
            less_prefix,
            power,
            modulus_bit,
            selector,
        }
    }

    fn assign(
        &self,
        mut layouter: impl Layouter<Fp>,
        source: &AssignedCell<Fp, Fp>,
        label: &str,
    ) -> Result<Vec<AssignedCell<Fp, Fp>>, Error> {
        let source_value = source.value().copied();
        let bits_lsb: Vec<Value<Fp>> = (0..FIELD_BITS)
            .map(|index| {
                source_value.map(|value| {
                    let repr = value.to_repr();
                    let bytes = repr.as_ref();
                    Fp::from(((bytes[index / 8] >> (index % 8)) & 1) as u64)
                })
            })
            .collect();
        let modulus_bits_lsb = modulus_bits_lsb();
        let bits_msb: Vec<Value<Fp>> = bits_lsb.iter().rev().cloned().collect();
        let modulus_bits_msb: Vec<bool> = modulus_bits_lsb.iter().rev().copied().collect();

        let mut accumulators = vec![Value::known(Fp::ZERO)];
        let mut equals = vec![Value::known(Fp::ONE)];
        let mut lesses = vec![Value::known(Fp::ZERO)];
        for row in 0..FIELD_BITS {
            let bit = bits_msb[row];
            let modulus = if modulus_bits_msb[row] {
                Fp::ONE
            } else {
                Fp::ZERO
            };
            let exponent = (FIELD_BITS - 1 - row) as u64;
            let power = Fp::from(2).pow_vartime([exponent, 0, 0, 0]);
            accumulators.push(accumulators[row] + bit * Value::known(power));
            let matches = bit * Value::known(modulus)
                + (Value::known(Fp::ONE) - bit) * Value::known(Fp::ONE - modulus);
            lesses.push(
                lesses[row] + equals[row] * Value::known(modulus) * (Value::known(Fp::ONE) - bit),
            );
            equals.push(equals[row] * matches);
        }

        layouter.assign_region(
            || format!("canonical bits {label}"),
            |mut region| {
                let mut assigned_msb = Vec::with_capacity(FIELD_BITS);
                let mut final_accumulator = None;
                let mut final_equal = None;
                let mut final_less = None;
                for row in 0..=FIELD_BITS {
                    let acc_cell = region.assign_advice(
                        || format!("accumulator {row}"),
                        self.accumulator,
                        row,
                        || accumulators[row],
                    )?;
                    let eq_cell = region.assign_advice(
                        || format!("equal prefix {row}"),
                        self.equal_prefix,
                        row,
                        || equals[row],
                    )?;
                    let less_cell = region.assign_advice(
                        || format!("less prefix {row}"),
                        self.less_prefix,
                        row,
                        || lesses[row],
                    )?;
                    if row == 0 {
                        region.constrain_constant(acc_cell.cell(), Fp::ZERO)?;
                        region.constrain_constant(eq_cell.cell(), Fp::ONE)?;
                        region.constrain_constant(less_cell.cell(), Fp::ZERO)?;
                    }
                    if row < FIELD_BITS {
                        self.selector.enable(&mut region, row)?;
                        region.assign_fixed(
                            || format!("power {row}"),
                            self.power,
                            row,
                            || {
                                let exponent = (FIELD_BITS - 1 - row) as u64;
                                Value::known(Fp::from(2).pow_vartime([exponent, 0, 0, 0]))
                            },
                        )?;
                        region.assign_fixed(
                            || format!("modulus bit {row}"),
                            self.modulus_bit,
                            row,
                            || Value::known(Fp::from(modulus_bits_msb[row] as u64)),
                        )?;
                        assigned_msb.push(region.assign_advice(
                            || format!("bit {row}"),
                            self.bit,
                            row,
                            || bits_msb[row],
                        )?);
                    } else {
                        final_accumulator = Some(acc_cell);
                        final_equal = Some(eq_cell);
                        final_less = Some(less_cell);
                    }
                }
                region.constrain_equal(final_accumulator.unwrap().cell(), source.cell())?;
                region.constrain_constant(final_equal.unwrap().cell(), Fp::ZERO)?;
                region.constrain_constant(final_less.unwrap().cell(), Fp::ONE)?;
                assigned_msb.reverse();
                Ok(assigned_msb)
            },
        )
    }
}

#[derive(Clone, Debug)]
struct ArithmeticConfig {
    a: Column<Advice>,
    b: Column<Advice>,
    c: Column<Advice>,
    coefficient: Column<Fixed>,
    q_noise_step: Selector,
    q_square_step: Selector,
    q_sum: Selector,
    q_small_coordinate: Selector,
    q_small_bit: Selector,
}

impl ArithmeticConfig {
    fn configure(meta: &mut ConstraintSystem<Fp>) -> Self {
        let a = meta.advice_column();
        let b = meta.advice_column();
        let c = meta.advice_column();
        for column in [a, b, c] {
            meta.enable_equality(column);
        }
        let coefficient = meta.fixed_column();
        let q_noise_step = meta.selector();
        let q_square_step = meta.selector();
        let q_sum = meta.selector();
        let q_small_coordinate = meta.selector();
        let q_small_bit = meta.selector();

        meta.create_gate("noise accumulation", |meta| {
            let q = meta.query_selector(q_noise_step);
            let running = meta.query_advice(a, Rotation::cur());
            let bit = meta.query_advice(b, Rotation::cur());
            let next = meta.query_advice(a, Rotation::next());
            let coeff = meta.query_fixed(coefficient);
            vec![q * (running + coeff * bit - next)]
        });
        meta.create_gate("squared norm accumulation", |meta| {
            let q = meta.query_selector(q_square_step);
            let running = meta.query_advice(a, Rotation::cur());
            let coordinate = meta.query_advice(b, Rotation::cur());
            let next = meta.query_advice(a, Rotation::next());
            vec![q * (running + coordinate.clone() * coordinate - next)]
        });
        meta.create_gate("sum equality", |meta| {
            let q = meta.query_selector(q_sum);
            let left = meta.query_advice(a, Rotation::cur());
            let right = meta.query_advice(b, Rotation::cur());
            let output = meta.query_advice(c, Rotation::cur());
            vec![q * (left + right - output)]
        });
        meta.create_gate("coordinate in {-1,0,1}", |meta| {
            let q = meta.query_selector(q_small_coordinate);
            let coordinate = meta.query_advice(a, Rotation::cur());
            let low = meta.query_advice(b, Rotation::cur());
            let high = meta.query_advice(c, Rotation::cur());
            let one = halo2_proofs::plonk::Expression::Constant(Fp::ONE);
            vec![
                q.clone() * low.clone() * (one.clone() - low.clone()),
                q.clone() * high.clone() * (one.clone() - high.clone()),
                q.clone() * low.clone() * high.clone(),
                q * (coordinate + one
                    - low
                    - high * halo2_proofs::plonk::Expression::Constant(Fp::from(2))),
            ]
        });
        meta.create_gate("small range bit", |meta| {
            let q = meta.query_selector(q_small_bit);
            let bit = meta.query_advice(b, Rotation::cur());
            let one = halo2_proofs::plonk::Expression::Constant(Fp::ONE);
            vec![q * bit.clone() * (one - bit)]
        });
        Self {
            a,
            b,
            c,
            coefficient,
            q_noise_step,
            q_square_step,
            q_sum,
            q_small_coordinate,
            q_small_bit,
        }
    }

    fn constrain_small_coordinate(
        &self,
        mut layouter: impl Layouter<Fp>,
        coordinate: &AssignedCell<Fp, Fp>,
        signed_value: Value<i64>,
        label: &str,
    ) -> Result<(), Error> {
        layouter.assign_region(
            || format!("small coordinate {label}"),
            |mut region| {
                self.q_small_coordinate.enable(&mut region, 0)?;
                coordinate.copy_advice(|| "coordinate", &mut region, self.a, 0)?;
                let encoded = signed_value.map(|value| (value + 1) as u64);
                region.assign_advice(
                    || "low bit",
                    self.b,
                    0,
                    || encoded.map(|value| Fp::from(value & 1)),
                )?;
                region.assign_advice(
                    || "high bit",
                    self.c,
                    0,
                    || encoded.map(|value| Fp::from((value >> 1) & 1)),
                )?;
                Ok(())
            },
        )
    }

    fn constrain_small_range(
        &self,
        mut layouter: impl Layouter<Fp>,
        source: &AssignedCell<Fp, Fp>,
        source_u64: Value<u64>,
        bits: usize,
        label: &str,
    ) -> Result<(), Error> {
        layouter.assign_region(
            || format!("small range {label}"),
            |mut region| {
                let mut running_value = Value::known(Fp::ZERO);
                let mut running_cell =
                    region.assign_advice(|| "range start", self.a, 0, || running_value)?;
                region.constrain_constant(running_cell.cell(), Fp::ZERO)?;
                for index in 0..bits {
                    self.q_noise_step.enable(&mut region, index)?;
                    let bit_value = source_u64.map(|value| Fp::from((value >> index) & 1));
                    self.q_small_bit.enable(&mut region, index)?;
                    region.assign_fixed(
                        || format!("range power {index}"),
                        self.coefficient,
                        index,
                        || Value::known(Fp::from(2).pow_vartime([index as u64, 0, 0, 0])),
                    )?;
                    region.assign_advice(
                        || format!("range bit {index}"),
                        self.b,
                        index,
                        || bit_value,
                    )?;
                    running_value = running_value
                        + bit_value
                            * Value::known(Fp::from(2).pow_vartime([index as u64, 0, 0, 0]));
                    running_cell = region.assign_advice(
                        || format!("range running {}", index + 1),
                        self.a,
                        index + 1,
                        || running_value,
                    )?;
                }
                region.constrain_equal(running_cell.cell(), source.cell())
            },
        )
    }
}

#[derive(Clone, Debug)]
struct VdpConfig {
    poseidon: Pow5Config<Fp, WIDTH, RATE>,
    canonical_bits: CanonicalBitsConfig,
    arithmetic: ArithmeticConfig,
    instance: Column<Instance>,
    witness: Column<Advice>,
}

#[derive(Clone, Debug)]
struct VdpCircuit {
    secret: Value<Fp>,
    salt: Value<Fp>,
    q_clipped: [Value<i64>; DIMENSION],
}

impl VdpCircuit {
    fn without_values() -> Self {
        Self {
            secret: Value::unknown(),
            salt: Value::unknown(),
            q_clipped: std::array::from_fn(|_| Value::unknown()),
        }
    }
}

impl Circuit<Fp> for VdpCircuit {
    type Config = VdpConfig;
    type FloorPlanner = SimpleFloorPlanner;

    fn without_witnesses(&self) -> Self {
        Self::without_values()
    }

    fn configure(meta: &mut ConstraintSystem<Fp>) -> Self::Config {
        let state: [Column<Advice>; WIDTH] = (0..WIDTH)
            .map(|_| meta.advice_column())
            .collect::<Vec<_>>()
            .try_into()
            .unwrap();
        let partial_sbox = meta.advice_column();
        let rc_a: [Column<Fixed>; WIDTH] = (0..WIDTH)
            .map(|_| meta.fixed_column())
            .collect::<Vec<_>>()
            .try_into()
            .unwrap();
        let rc_b: [Column<Fixed>; WIDTH] = (0..WIDTH)
            .map(|_| meta.fixed_column())
            .collect::<Vec<_>>()
            .try_into()
            .unwrap();
        meta.enable_constant(rc_b[0]);
        let poseidon = PoseidonChip::configure::<P128Pow5T3>(meta, state, partial_sbox, rc_a, rc_b);
        let canonical_bits = CanonicalBitsConfig::configure(meta);
        let arithmetic = ArithmeticConfig::configure(meta);
        let instance = meta.instance_column();
        meta.enable_equality(instance);
        let witness = meta.advice_column();
        meta.enable_equality(witness);
        VdpConfig {
            poseidon,
            canonical_bits,
            arithmetic,
            instance,
            witness,
        }
    }

    fn synthesize(
        &self,
        config: Self::Config,
        mut layouter: impl Layouter<Fp>,
    ) -> Result<(), Error> {
        let public_cells = layouter.assign_region(
            || "load public statement",
            |mut region| {
                let mut cells = Vec::with_capacity(INSTANCE_Q_NOISY_START + DIMENSION);
                for row in 0..(INSTANCE_Q_NOISY_START + DIMENSION) {
                    let cell = region.assign_advice_from_instance(
                        || format!("public input {row}"),
                        config.instance,
                        row,
                        config.witness,
                        row,
                    )?;
                    cells.push(cell);
                }
                Ok(cells)
            },
        )?;
        let private_cells = layouter.assign_region(
            || "load private witness",
            |mut region| {
                let secret =
                    region.assign_advice(|| "client secret", config.witness, 0, || self.secret)?;
                let salt =
                    region.assign_advice(|| "update salt", config.witness, 1, || self.salt)?;
                let mut q_cells = Vec::with_capacity(DIMENSION);
                for (index, signed) in self.q_clipped.iter().enumerate() {
                    q_cells.push(region.assign_advice(
                        || format!("q clipped {index}"),
                        config.witness,
                        index + 2,
                        || signed.map(fp_from_i64),
                    )?);
                }
                Ok((secret, salt, q_cells))
            },
        )?;
        let (secret, salt, q_cells) = private_cells;
        for (index, coordinate) in q_cells.iter().enumerate() {
            config.arithmetic.constrain_small_coordinate(
                layouter.namespace(|| format!("coordinate range {index}")),
                coordinate,
                self.q_clipped[index],
                &format!("q{index}"),
            )?;
        }

        let tag_secret = assign_constant(
            layouter.namespace(|| "secret tag"),
            config.witness,
            Fp::from(TAG_SECRET),
        )?;
        let tag_update = assign_constant(
            layouter.namespace(|| "update tag"),
            config.witness,
            Fp::from(TAG_UPDATE),
        )?;
        let tag_context = assign_constant(
            layouter.namespace(|| "context tag"),
            config.witness,
            Fp::from(TAG_CONTEXT),
        )?;
        let tag_prg = assign_constant(
            layouter.namespace(|| "prg tag"),
            config.witness,
            Fp::from(TAG_PRG),
        )?;

        let secret_domain = circuit_hash2(
            config.poseidon.clone(),
            layouter.namespace(|| "secret domain"),
            tag_secret,
            public_cells[INSTANCE_CLIENT_ID].clone(),
        )?;
        let computed_secret_commitment = circuit_hash2(
            config.poseidon.clone(),
            layouter.namespace(|| "secret commitment"),
            secret_domain,
            secret.clone(),
        )?;
        constrain_equal(
            layouter.namespace(|| "check secret commitment"),
            config.witness,
            &computed_secret_commitment,
            &public_cells[INSTANCE_SECRET_COMMITMENT],
        )?;

        let mut computed_update_commitment = circuit_hash2(
            config.poseidon.clone(),
            layouter.namespace(|| "update commitment init"),
            tag_update,
            salt,
        )?;
        for (index, coordinate) in q_cells.iter().enumerate() {
            computed_update_commitment = circuit_hash2(
                config.poseidon.clone(),
                layouter.namespace(|| format!("update commitment fold {index}")),
                computed_update_commitment,
                coordinate.clone(),
            )?;
        }
        constrain_equal(
            layouter.namespace(|| "check update commitment"),
            config.witness,
            &computed_update_commitment,
            &public_cells[INSTANCE_UPDATE_COMMITMENT],
        )?;

        let context_fields = [
            INSTANCE_CLIENT_ID,
            INSTANCE_ROUND_ID,
            INSTANCE_MODEL_HASH,
            INSTANCE_NONCE,
            INSTANCE_UPDATE_COMMITMENT,
            INSTANCE_CHALLENGE,
        ];
        let mut context = tag_context;
        for (position, field_index) in context_fields.iter().enumerate() {
            context = circuit_hash2(
                config.poseidon.clone(),
                layouter.namespace(|| format!("context fold {position}")),
                context,
                public_cells[*field_index].clone(),
            )?;
        }
        let prg_key = circuit_hash2(
            config.poseidon.clone(),
            layouter.namespace(|| "context-bound PRG key"),
            secret,
            context,
        )?;

        for index in 0..DIMENSION {
            let index_cell = assign_constant(
                layouter.namespace(|| format!("PRG index {index}")),
                config.witness,
                Fp::from(index as u64),
            )?;
            let indexed = circuit_hash2(
                config.poseidon.clone(),
                layouter.namespace(|| format!("PRG index domain {index}")),
                tag_prg.clone(),
                index_cell,
            )?;
            let prg_output = circuit_hash2(
                config.poseidon.clone(),
                layouter.namespace(|| format!("PRG output {index}")),
                prg_key.clone(),
                indexed,
            )?;
            let bits = config.canonical_bits.assign(
                layouter.namespace(|| format!("canonical PRG bits {index}")),
                &prg_output,
                &format!("prg{index}"),
            )?;
            constrain_noisy_coordinate(
                &config.arithmetic,
                layouter.namespace(|| format!("noise relation {index}")),
                &q_cells[index],
                &bits[..(2 * BINOMIAL_K)],
                &public_cells[INSTANCE_Q_NOISY_START + index],
            )?;
        }

        let (norm_cell, norm_value) = constrain_squared_norm(
            &config.arithmetic,
            layouter.namespace(|| "squared norm"),
            &q_cells,
            &self.q_clipped,
        )?;
        let clip_bound = &public_cells[INSTANCE_CLIP_BOUND_SQ];
        let fixed_clip_bound = assign_constant(
            layouter.namespace(|| "fixed clip profile"),
            config.witness,
            Fp::from(CLIP_BOUND_SQ),
        )?;
        constrain_equal(
            layouter.namespace(|| "check fixed clip profile"),
            config.witness,
            &fixed_clip_bound,
            clip_bound,
        )?;
        let clip_bound_value = clip_bound.value().copied();
        let slack_value = clip_bound_value - norm_value;
        let slack_u64 = self
            .q_clipped
            .iter()
            .fold(Value::known(0_i64), |acc, value| {
                acc + value.map(|coordinate| coordinate * coordinate)
            });
        let slack_u64 = slack_u64.map(|norm| CLIP_BOUND_SQ.saturating_sub(norm as u64));
        let slack_cell = layouter.assign_region(
            || "clip slack",
            |mut region| region.assign_advice(|| "clip slack", config.witness, 0, || slack_value),
        )?;
        config.arithmetic.constrain_small_range(
            layouter.namespace(|| "clip slack range"),
            &slack_cell,
            slack_u64,
            3,
            "clip slack",
        )?;
        constrain_sum(
            &config.arithmetic,
            layouter.namespace(|| "clip bound equality"),
            &norm_cell,
            &slack_cell,
            clip_bound,
        )?;
        Ok(())
    }
}

fn modulus_bits_lsb() -> Vec<bool> {
    let text = Fp::MODULUS;
    let modulus = if let Some(hex) = text.strip_prefix("0x") {
        BigUint::parse_bytes(hex.as_bytes(), 16).unwrap()
    } else {
        BigUint::parse_bytes(text.as_bytes(), 10).unwrap()
    };
    (0..FIELD_BITS)
        .map(|index| modulus.bit(index as u64))
        .collect()
}

fn fp_from_i64(value: i64) -> Fp {
    if value >= 0 {
        Fp::from(value as u64)
    } else {
        -Fp::from((-value) as u64)
    }
}

fn assign_constant(
    mut layouter: impl Layouter<Fp>,
    column: Column<Advice>,
    value: Fp,
) -> Result<AssignedCell<Fp, Fp>, Error> {
    layouter.assign_region(
        || "assign constant",
        |mut region| region.assign_advice_from_constant(|| "constant", column, 0, value),
    )
}

fn circuit_hash2(
    poseidon_config: Pow5Config<Fp, WIDTH, RATE>,
    mut layouter: impl Layouter<Fp>,
    left: AssignedCell<Fp, Fp>,
    right: AssignedCell<Fp, Fp>,
) -> Result<AssignedCell<Fp, Fp>, Error> {
    let chip = PoseidonChip::construct(poseidon_config);
    let hasher = Hash::<_, _, P128Pow5T3, ConstantLength<2>, WIDTH, RATE>::init(
        chip,
        layouter.namespace(|| "init"),
    )?;
    hasher.hash(layouter.namespace(|| "hash"), [left, right])
}

fn native_hash2(left: Fp, right: Fp) -> Fp {
    poseidon::Hash::<Fp, P128Pow5T3, ConstantLength<2>, WIDTH, RATE>::init().hash([left, right])
}

fn constrain_equal(
    mut layouter: impl Layouter<Fp>,
    column: Column<Advice>,
    left: &AssignedCell<Fp, Fp>,
    right: &AssignedCell<Fp, Fp>,
) -> Result<(), Error> {
    layouter.assign_region(
        || "copy equality",
        |mut region| {
            let left_copy = left.copy_advice(|| "left", &mut region, column, 0)?;
            let right_copy = right.copy_advice(|| "right", &mut region, column, 1)?;
            region.constrain_equal(left_copy.cell(), right_copy.cell())
        },
    )
}

fn constrain_noisy_coordinate(
    config: &ArithmeticConfig,
    mut layouter: impl Layouter<Fp>,
    q_clipped: &AssignedCell<Fp, Fp>,
    bits: &[AssignedCell<Fp, Fp>],
    q_noisy: &AssignedCell<Fp, Fp>,
) -> Result<(), Error> {
    assert_eq!(bits.len(), 2 * BINOMIAL_K);
    layouter.assign_region(
        || "centered-binomial relation",
        |mut region| {
            let mut running_value = q_clipped.value().copied();
            let mut running_cell =
                q_clipped.copy_advice(|| "q clipped", &mut region, config.a, 0)?;
            for (index, bit) in bits.iter().enumerate() {
                config.q_noise_step.enable(&mut region, index)?;
                let coefficient = if index < BINOMIAL_K {
                    NOISE_UNIT
                } else {
                    -NOISE_UNIT
                };
                region.assign_fixed(
                    || format!("noise coefficient {index}"),
                    config.coefficient,
                    index,
                    || Value::known(fp_from_i64(coefficient)),
                )?;
                bit.copy_advice(
                    || format!("noise bit {index}"),
                    &mut region,
                    config.b,
                    index,
                )?;
                running_value =
                    running_value + bit.value().copied() * Value::known(fp_from_i64(coefficient));
                running_cell = region.assign_advice(
                    || format!("running noisy value {}", index + 1),
                    config.a,
                    index + 1,
                    || running_value,
                )?;
            }
            region.constrain_equal(running_cell.cell(), q_noisy.cell())
        },
    )
}

fn constrain_squared_norm(
    config: &ArithmeticConfig,
    mut layouter: impl Layouter<Fp>,
    q_cells: &[AssignedCell<Fp, Fp>],
    q_values: &[Value<i64>; DIMENSION],
) -> Result<(AssignedCell<Fp, Fp>, Value<Fp>), Error> {
    layouter.assign_region(
        || "integer squared norm",
        |mut region| {
            let mut running_value = Value::known(Fp::ZERO);
            let mut running_cell =
                region.assign_advice(|| "norm start", config.a, 0, || running_value)?;
            region.constrain_constant(running_cell.cell(), Fp::ZERO)?;
            for index in 0..DIMENSION {
                config.q_square_step.enable(&mut region, index)?;
                q_cells[index].copy_advice(
                    || format!("norm coordinate {index}"),
                    &mut region,
                    config.b,
                    index,
                )?;
                running_value =
                    running_value + q_values[index].map(|value| fp_from_i64(value * value));
                running_cell = region.assign_advice(
                    || format!("norm running {}", index + 1),
                    config.a,
                    index + 1,
                    || running_value,
                )?;
            }
            Ok((running_cell, running_value))
        },
    )
}

fn constrain_sum(
    config: &ArithmeticConfig,
    mut layouter: impl Layouter<Fp>,
    left: &AssignedCell<Fp, Fp>,
    right: &AssignedCell<Fp, Fp>,
    output: &AssignedCell<Fp, Fp>,
) -> Result<(), Error> {
    layouter.assign_region(
        || "sum relation",
        |mut region| {
            config.q_sum.enable(&mut region, 0)?;
            left.copy_advice(|| "left", &mut region, config.a, 0)?;
            right.copy_advice(|| "right", &mut region, config.b, 0)?;
            output.copy_advice(|| "output", &mut region, config.c, 0)?;
            Ok(())
        },
    )
}

#[derive(Clone)]
struct DemoBundle {
    circuit: VdpCircuit,
    instances: Vec<Fp>,
    q_noisy: [i64; DIMENSION],
}

fn demo_bundle(experiment_seed: u64) -> DemoBundle {
    demo_bundle_with_material(
        experiment_seed,
        Fp::random(OsRng),
        Fp::random(OsRng),
        Fp::random(OsRng),
    )
}

fn demo_bundle_with_material(
    experiment_seed: u64,
    secret: Fp,
    salt: Fp,
    challenge: Fp,
) -> DemoBundle {
    contextual_bundle(
        [1_i64, -1, 0, 1],
        [
            Fp::from(7),
            Fp::from(11),
            Fp::from(0xabc0_1234),
            Fp::from(0x9001 ^ experiment_seed.rotate_left(17)),
        ],
        secret,
        salt,
        challenge,
    )
}

fn update_commitment_for(q_clipped: [i64; DIMENSION], salt: Fp) -> Fp {
    let mut commitment = native_hash2(Fp::from(TAG_UPDATE), salt);
    for coordinate in q_clipped {
        commitment = native_hash2(commitment, fp_from_i64(coordinate));
    }
    commitment
}

fn contextual_bundle(
    q_clipped: [i64; DIMENSION],
    context: [Fp; 4],
    secret: Fp,
    salt: Fp,
    challenge: Fp,
) -> DemoBundle {
    let [client_id, round_id, model_hash, nonce] = context;

    let secret_domain = native_hash2(Fp::from(TAG_SECRET), client_id);
    let secret_commitment = native_hash2(secret_domain, secret);
    let update_commitment = update_commitment_for(q_clipped, salt);
    let mut context = Fp::from(TAG_CONTEXT);
    for field in [
        client_id,
        round_id,
        model_hash,
        nonce,
        update_commitment,
        challenge,
    ] {
        context = native_hash2(context, field);
    }
    let prg_key = native_hash2(secret, context);
    let mut q_noise = [0_i64; DIMENSION];
    let mut q_noisy = [0_i64; DIMENSION];
    for index in 0..DIMENSION {
        let indexed = native_hash2(Fp::from(TAG_PRG), Fp::from(index as u64));
        let output = native_hash2(prg_key, indexed);
        let repr = output.to_repr();
        let bytes = repr.as_ref();
        let mut positive = 0_i64;
        let mut negative = 0_i64;
        for bit in 0..BINOMIAL_K {
            positive += ((bytes[bit / 8] >> (bit % 8)) & 1) as i64;
        }
        for bit in BINOMIAL_K..(2 * BINOMIAL_K) {
            negative += ((bytes[bit / 8] >> (bit % 8)) & 1) as i64;
        }
        q_noise[index] = (positive - negative) * NOISE_UNIT;
        q_noisy[index] = q_clipped[index] + q_noise[index];
    }
    let mut instances = vec![
        client_id,
        round_id,
        model_hash,
        nonce,
        challenge,
        secret_commitment,
        update_commitment,
        Fp::from(4),
    ];
    instances.extend(q_noisy.iter().map(|value| fp_from_i64(*value)));
    DemoBundle {
        circuit: VdpCircuit {
            secret: Value::known(secret),
            salt: Value::known(salt),
            q_clipped: q_clipped.map(Value::known),
        },
        instances,
        q_noisy,
    }
}

#[derive(Serialize)]
struct ProofReport {
    experiment_seed: u64,
    secret_source: &'static str,
    salt_source: &'static str,
    challenge_source: &'static str,
    backend: &'static str,
    curve: &'static str,
    circuit_k: u32,
    rows_capacity: usize,
    dimension: usize,
    centered_binomial_k: usize,
    noise_unit: i64,
    q_noisy: [i64; DIMENSION],
    public_instances_le_hex: Vec<String>,
    public_instance_count: usize,
    mock_prover_satisfied: bool,
    proof_verified: bool,
    proof_bytes: usize,
    proof_sha256: String,
    keygen_seconds: f64,
    prove_seconds: f64,
    verify_seconds: f64,
    private_values_written_to_public_statement: bool,
    low_entropy_private_hashes_emitted: bool,
    claim_scope: &'static str,
}

fn prove(bundle: DemoBundle, experiment_seed: u64, output_path: PathBuf) -> ProofReport {
    let mock = MockProver::run(CIRCUIT_K, &bundle.circuit, vec![bundle.instances.clone()])
        .expect("mock prover should synthesize");
    mock.assert_satisfied();

    let params: Params<EqAffine> = Params::new(CIRCUIT_K);
    let keygen_start = Instant::now();
    let vk = plonk::keygen_vk(&params, &bundle.circuit).expect("verification key");
    let pk = plonk::keygen_pk(&params, vk, &bundle.circuit).expect("proving key");
    let keygen_seconds = keygen_start.elapsed().as_secs_f64();

    let prove_start = Instant::now();
    let mut transcript = Blake2bWrite::<_, EqAffine, Challenge255<_>>::init(vec![]);
    plonk::create_proof(
        &params,
        &pk,
        &[bundle.circuit.clone()],
        &[&[&bundle.instances]],
        OsRng,
        &mut transcript,
    )
    .expect("proof generation");
    let proof = transcript.finalize();
    let prove_seconds = prove_start.elapsed().as_secs_f64();

    let verify_start = Instant::now();
    let strategy = SingleVerifier::new(&params);
    let mut reader = Blake2bRead::<_, EqAffine, Challenge255<_>>::init(&proof[..]);
    let proof_verified = plonk::verify_proof(
        &params,
        pk.get_vk(),
        strategy,
        &[&[&bundle.instances]],
        &mut reader,
    )
    .is_ok();
    let verify_seconds = verify_start.elapsed().as_secs_f64();

    let digest = Sha256::digest(&proof);
    let proof_sha256 = digest
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>();
    let proof_path = output_path.with_extension("proof.bin");
    fs::create_dir_all(output_path.parent().unwrap()).expect("create results directory");
    fs::write(&proof_path, &proof).expect("write proof bytes");

    ProofReport {
        experiment_seed,
        secret_source: "operating-system CSPRNG",
        salt_source: "operating-system CSPRNG",
        challenge_source:
            "operating-system CSPRNG; commit-before-challenge ordering is host-enforced",
        backend: "zcash-halo2-ipa",
        curve: "Pasta/EqAffine",
        circuit_k: CIRCUIT_K,
        rows_capacity: 1_usize << CIRCUIT_K,
        dimension: DIMENSION,
        centered_binomial_k: BINOMIAL_K,
        noise_unit: NOISE_UNIT,
        q_noisy: bundle.q_noisy,
        public_instances_le_hex: bundle.instances.iter().map(fp_le_hex).collect(),
        public_instance_count: bundle.instances.len(),
        mock_prover_satisfied: true,
        proof_verified,
        proof_bytes: proof.len(),
        proof_sha256,
        keygen_seconds,
        prove_seconds,
        verify_seconds,
        private_values_written_to_public_statement: false,
        low_entropy_private_hashes_emitted: false,
        claim_scope:
            "actual context-bound discrete-noise circuit; not full local-training provenance",
    }
}

fn fp_le_hex(value: &Fp) -> String {
    value
        .to_repr()
        .as_ref()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn main() {
    let arguments: Vec<String> = std::env::args().collect();
    if arguments.get(1).map(String::as_str) == Some("--federated") {
        federated::run(&arguments[2..]);
        return;
    }
    if arguments.get(1).map(String::as_str) == Some("--verify-federated") {
        federated::verify_saved(&PathBuf::from(arguments.get(2).expect("run.json path")));
        return;
    }
    let output = arguments
        .get(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("results/halo2_context_noise_proof.json"));
    let experiment_seed = arguments
        .get(2)
        .map(|value| value.parse::<u64>().expect("seed must be a u64"))
        .unwrap_or(42);
    let report = prove(
        demo_bundle(experiment_seed),
        experiment_seed,
        output.clone(),
    );
    fs::write(
        &output,
        serde_json::to_string_pretty(&report).expect("serialize report"),
    )
    .expect("write report");
    println!(
        "Halo2 proof verified={} bytes={} prove={:.3}s verify={:.3}s",
        report.proof_verified, report.proof_bytes, report.prove_seconds, report.verify_seconds
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_bundle() -> DemoBundle {
        demo_bundle_with_material(
            42,
            Fp::from(0x5ec0_0001),
            Fp::from(0x5a17),
            Fp::from(0xcafe_2026),
        )
    }

    #[test]
    fn honest_circuit_is_satisfied() {
        let bundle = test_bundle();
        let prover = MockProver::run(CIRCUIT_K, &bundle.circuit, vec![bundle.instances]).unwrap();
        prover.assert_satisfied();
    }

    #[test]
    fn tampered_noisy_update_is_rejected() {
        let mut bundle = test_bundle();
        bundle.instances[INSTANCE_Q_NOISY_START] += Fp::ONE;
        let prover = MockProver::run(CIRCUIT_K, &bundle.circuit, vec![bundle.instances]).unwrap();
        assert!(prover.verify().is_err());
    }

    #[test]
    fn swapped_round_context_is_rejected() {
        let mut bundle = test_bundle();
        bundle.instances[INSTANCE_ROUND_ID] += Fp::ONE;
        let prover = MockProver::run(CIRCUIT_K, &bundle.circuit, vec![bundle.instances]).unwrap();
        assert!(prover.verify().is_err());
    }

    #[test]
    fn zero_noise_forgery_is_rejected() {
        let mut bundle = test_bundle();
        let claimed_clipped = [1_i64, -1, 0, 1];
        for index in 0..DIMENSION {
            bundle.instances[INSTANCE_Q_NOISY_START + index] = fp_from_i64(claimed_clipped[index]);
        }
        let prover = MockProver::run(CIRCUIT_K, &bundle.circuit, vec![bundle.instances]).unwrap();
        assert!(prover.verify().is_err());
    }
}
