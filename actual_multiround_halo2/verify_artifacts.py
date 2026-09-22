"""Check frozen evidence bytes locally or in Git's normalized stored blobs."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--results-dir',type=Path,default=Path(__file__).parent/'results_roundtrip')
parser.add_argument('--git-revision',help='Additionally compare Git blobs, e.g. HEAD')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
directory = args.results_dir.resolve()
manifest = json.loads((directory/'artifact_sha256.json').read_text())
for relative,expected in manifest.items():
    path = directory/relative
    assert path.resolve().is_relative_to(directory), 'manifest path escapes results'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, relative
    if args.git_revision:
        spec = f'{args.git_revision}:{path.relative_to(root).as_posix()}'
        blob = subprocess.check_output(['git','show',spec],cwd=root)
        assert hashlib.sha256(blob).hexdigest() == expected, f'Git blob mismatch: {relative}'
print(f'validated_artifacts={len(manifest)} git_blobs_checked={bool(args.git_revision)}')
