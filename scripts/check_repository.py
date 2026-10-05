"""Fail CI when the repository drifts back into an unreviewable layout."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


REPO = Path(__file__).resolve().parents[1]
EXPERIMENTS = {
    "actual_multiround_halo2",
    "adult_income_model",
    "baseline_charts",
    "binary_dataset_repeatability",
    "breast_cancer_repeatability",
    "canonical_witness",
    "clipping_verification",
    "constraint_artifacts",
    "constraint_profile",
    "context_bound_randomness_protocol",
    "covertype_large_dataset_scaling",
    "cross_backend_reproducibility",
    "discrete_noise_accounting",
    "dp_fedavg_baseline",
    "end_to_end_proof_gated_round",
    "experimental_rigor_audit",
    "ezkl_constraint_integration",
    "fedavg_baseline",
    "fedavg_round_charts",
    "gaussian_privacy_accounting",
    "halo2_verifiable_randomness",
    "multiclass_repeatability",
    "multiclass_vdp_zk",
    "multiround_threat_matrix",
    "noise_relation_verification",
    "noniid_client_scaling",
    "privacy_utility_sweep",
    "production_scaling",
    "proof_gated_round",
    "quantization_scale_sweep",
    "quantized_constraint_analysis",
    "robust_aggregation",
    "zk_backend_bundle",
    "zk_cost_scaling",
    "zk_ezkl_demo",
}
TEXT_SUFFIXES = {".md", ".py", ".txt", ".toml", ".yml", ".yaml"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
TEMPORARY_BRANCH_MARKER = "tree/" + "codex/"
RENAME_ARTIFACT = "Halo2 verifiable-randomness circuit/" + "31"


def repository_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO,
    ).decode("utf-8")
    return [Path(item) for item in output.split("\0") if item]


def check_markdown_links(path: Path) -> list[str]:
    errors: list[str] = []
    text = (REPO / path).read_text(encoding="utf-8")
    for raw_target in LINK.findall(text):
        target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        local_target = unquote(target.split("#", 1)[0])
        resolved = (REPO / path.parent / local_target).resolve()
        if not resolved.exists():
            errors.append(f"broken local link: {path} -> {local_target}")
    return errors


def main() -> int:
    errors: list[str] = []
    experiment_root = REPO / "experiments"
    actual = {
        path.name
        for path in experiment_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    missing = EXPERIMENTS - actual
    unexpected = actual - EXPERIMENTS
    if missing:
        errors.append(f"missing experiment directories: {sorted(missing)}")
    if unexpected:
        errors.append(f"unregistered experiment directories: {sorted(unexpected)}")

    for name in sorted(EXPERIMENTS):
        if not (experiment_root / name / "README.md").is_file():
            errors.append(f"experiment has no README: experiments/{name}")
        if (REPO / name).exists():
            errors.append(f"legacy top-level experiment directory exists: {name}")

    files = repository_files()
    for path in files:
        normalized = path.as_posix()
        if path.suffix in {".key", ".srs"}:
            errors.append(f"generated proving artifact is tracked: {normalized}")
        if "__pycache__" in path.parts or "target" in path.parts:
            errors.append(f"build/cache artifact is tracked: {normalized}")
        if normalized.startswith("experiments/adult_income_model/data/") and (
            "/raw/" in normalized
            or "/processed/" in normalized
            or ("/clients/" in normalized and path.suffix == ".npy")
        ):
            errors.append(f"downloaded or derived dataset is tracked: {normalized}")

        absolute = REPO / path
        if path.suffix.lower() in TEXT_SUFFIXES and absolute.is_file():
            text = absolute.read_text(encoding="utf-8")
            if TEMPORARY_BRANCH_MARKER in text:
                errors.append(f"temporary branch URL remains in: {normalized}")
            if RENAME_ARTIFACT in text:
                errors.append(f"automatic rename artifact remains in: {normalized}")
        if path.suffix.lower() == ".md" and absolute.is_file():
            errors.extend(check_markdown_links(path))

    required = [
        "README.md",
        "experiments/README.md",
        "docs/README.md",
        "docs/research/threat-model.md",
        "docs/research/claim-evidence-map.md",
        "docs/governance/ai-assistance.md",
    ]
    for relative in required:
        if not (REPO / relative).is_file():
            errors.append(f"required project entry point is missing: {relative}")

    if errors:
        print("Repository hygiene check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"Repository hygiene check passed: {len(EXPERIMENTS)} experiments, "
        f"{len(files)} versioned or pending files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
