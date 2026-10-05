# discrete-noise accounting Exact Centered-Binomial Privacy Accounting

## Primary circuit profile

- k=16, replace-one coordinate shift=2.
- Compositions=40 (dimension x rounds).
- Target delta=1e-05.
- Conservative epsilon upper=28.840669.
- Accounted total delta upper=1e-05.
- Finite-support unavoidable delta floor=3.07336403576e-07.
- Field low-bit statistical-distance bound=5.935e-66.

The result is information-theoretic for ideal independent uniform sampler bits. The
actual Poseidon construction gives computational DP under an explicit PRF assumption,
with the PRF distinguishing advantage added to delta. Unique contexts are mandatory.

The accountant is for the exact finite centered-binomial support; it does not reuse a
Gaussian RDP formula. Privacy-loss values are rounded upward before convolution and the
reported delta includes the declared numerical guard.