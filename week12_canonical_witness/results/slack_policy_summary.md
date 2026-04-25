# Week 12 Slack Policy Sweep Summary

- Max honest excess observed (ppm): 4200.0
- Min tampered excess observed (ppm): 73300.0
- Feasible slack interval (ppm): (4200.0, 73300.0)
- Simple candidate slack (ppm): 4201

Policy comparison:
- slack_ppm=0: honest_accept=5/9, tampered_reject=9/9, max_honest_excess_ppm=4200.0, min_tampered_excess_ppm=73300.0
- slack_ppm=100: honest_accept=5/9, tampered_reject=9/9, max_honest_excess_ppm=4200.0, min_tampered_excess_ppm=73300.0
- slack_ppm=500: honest_accept=7/9, tampered_reject=9/9, max_honest_excess_ppm=4200.0, min_tampered_excess_ppm=73300.0
- slack_ppm=1000: honest_accept=8/9, tampered_reject=9/9, max_honest_excess_ppm=4200.0, min_tampered_excess_ppm=73300.0
- slack_ppm=5000: honest_accept=9/9, tampered_reject=9/9, max_honest_excess_ppm=4200.0, min_tampered_excess_ppm=73300.0
- slack_ppm=20000: honest_accept=9/9, tampered_reject=9/9, max_honest_excess_ppm=4200.0, min_tampered_excess_ppm=73300.0

Interpretation:
- A usable slack policy should accept all honest clipped witnesses while still rejecting intentionally enlarged clipped updates.
- If the gap between max honest excess and min tampered excess is wide enough, the future circuit can encode a fixed slack threshold with low ambiguity.
- In this run, a slack slightly above the max honest excess is enough to preserve honest cases while keeping a large margin from the tampered cases.