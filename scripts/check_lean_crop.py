"""Check Lean crop proofs and compare finite fixtures with the real Pillow pipeline."""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from app.imaging import auto_box

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean", help="Path to the pinned Lean 4.19.0 executable")
    args = parser.parse_args()
    started = time.monotonic()
    version = subprocess.run(
        [args.lean, "--version"], capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()
    if "version 4.19.0," not in version:
        raise RuntimeError(f"Expected the toolchain in formal/lean-toolchain; got {version}")
    proof = ROOT / "formal" / "Crop.lean"
    checked = subprocess.run(
        [args.lean, "--run", str(proof)], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=120,
    )
    dependencies = re.findall(r"depends on axioms: \[([^\]]*)\]", checked.stdout)
    standard_axioms = {"propext", "Classical.choice", "Quot.sound"}
    if len(dependencies) != 5 or "warning:" in checked.stdout:
        raise RuntimeError("Expected five audited theorem dependency lists without warnings")
    for dependency in dependencies:
        if set(dependency.split(", ")) - standard_axioms:
            raise RuntimeError("Proof uses an admitted proof or a nonstandard axiom")
    cases = [line for line in checked.stdout.splitlines() if line.startswith("CASE,")]
    if len(cases) != 7644:
        raise RuntimeError(f"Expected 7644 Lean fixtures, got {len(cases)}")
    for case in cases:
        _, extent, left, right, padding, start, end = case.split(",")
        extent, left, right, padding, start, end = map(
            int, (extent, left, right, padding, start, end)
        )
        for transparent in (False, True):
            for vertical in (False, True):
                size = (3, extent) if vertical else (extent, 3)
                foreground = (1, left, 2, right) if vertical else (left, 1, right, 2)
                image = Image.new("RGBA", size, (0, 0, 0, 0) if transparent else "white")
                image.paste("white" if transparent else "black", foreground)
                actual, warning = auto_box(image, padding, 254)
                cross_start, cross_end = max(0, 1 - padding), min(3, 2 + padding)
                expected = ([cross_start, start, cross_end, end] if vertical
                            else [start, cross_start, end, cross_end])
                if actual != expected or warning is not None:
                    raise AssertionError((case, transparent, vertical, actual, warning, expected))
    # An intentionally wrong specification must fail mathematical verification.
    # This is a sensitivity check, not a bug found in the production algorithm.
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lean-crop-", dir=work) as temporary:
        mutant = Path(temporary) / "NegativeCrop.lean"
        source = proof.read_text(encoding="utf-8")
        if source.count("left - padding") != 1:
            raise RuntimeError("Negative-control mutation no longer matches the specification")
        mutant.write_text(source.replace("left - padding", "left + padding"), encoding="utf-8")
        rejected = subprocess.run(
            [args.lean, str(mutant)], cwd=ROOT,
            capture_output=True, text=True, timeout=120,
        )
        if rejected.returncode == 0 or "omega" not in rejected.stdout:
            raise RuntimeError("The invalid-padding control was not rejected by the proof checker")
    report = {
        "lean": version,
        "theorems_checked": len(dependencies),
        "admitted_proofs": 0,
        "lean_fixtures": len(cases),
        "pillow_comparisons": len(cases) * 4,
        "negative_control_rejected": True,
        "conformance_failures": 0,
        "seconds": round(time.monotonic() - started, 3),
        "scope": "Padding of valid detected foreground bounds; not segmentation accuracy or Python proof",
    }
    (work / "lean-crop-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
