# Week 18 End-to-End S2 Round Summary

- Initial accuracy: 0.694851
- Proof-gated next-round accuracy: 0.839697
- Ungated next-round accuracy: 0.836831
- Accepted clients: 2/3

Interpretation:
- This round applies the proof-gated aggregate back to the global model and measures the resulting accuracy.
- The ungated comparison shows what would happen if the server ignored the proof/check outcome and aggregated every submitted update.
- This is the closest repo-level prototype to an end-to-end FL + VDP + ZK round outcome.