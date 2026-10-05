# discrete-noise accounting — Exact discrete-noise accountant

This experiment supplies the privacy theorem and executable accountant for the
exact centered-binomial sampler implemented by the Halo2 verifiable-randomness circuit.

It deliberately does not substitute a Gaussian RDP formula. The implementation
tracks finite-support failures, composes privacy-loss distributions, rounds
privacy losses upward, adds a numerical guard, and includes the low-bit bias
bound for a uniform Pasta field output.

Run:

```powershell
python experiments/discrete_noise_accounting/centered_binomial_accountant.py
python -m unittest discover -s experiments/discrete_noise_accounting -p "test*.py" -v
```

The ideal mechanism receives an information-theoretic `(epsilon, delta)` result.
The actual Poseidon construction receives a conditional computational-DP result
under the PRF and unique-context assumptions stated in `formal_dp_theorem.md`.
The primary `d=4`, `k=16`, ten-round profile uses replacement client-level
adjacency and fixed participation. Add/remove participation privacy is outside
the stated guarantee.
