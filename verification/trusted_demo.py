"""RED → GREEN verification for the bundled, trusted demonstration only."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEMO_SOURCE = ROOT / "sample_app"


def run_trusted_demo_verification() -> dict:
    """Run pytest before and after patching a temporary demo copy.

    User-supplied code never reaches this function.  The original demo source is
    also never changed.
    """
    with tempfile.TemporaryDirectory(prefix="bugsleuth_demo_verify_") as temp:
        root = Path(temp)
        package = root / "sample_app"
        shutil.copytree(DEMO_SOURCE, package, ignore=shutil.ignore_patterns("__pycache__"))
        test_file = root / "test_regression.py"
        test_file.write_text(
            "from sample_app.payment_service import process_payment\n\n"
            "def test_zero_value_payment_is_accepted():\n"
            "    assert process_payment(0) == 'Payment processed'\n",
            encoding="utf-8",
        )
        before = _run_pytest(root, test_file)

        service = package / "payment_service.py"
        original = service.read_text(encoding="utf-8")
        patched = original.replace("if not payment_amount:", "if payment_amount is None:", 1)
        if patched == original:
            return {"status": "error", "error": "Trusted demo patch could not be applied."}
        service.write_text(patched, encoding="utf-8")
        after = _run_pytest(root, test_file)

    status = "verified" if before["failed"] > 0 and after["failed"] == 0 else "failed"
    return {
        "status": status,
        "scope": "trusted_demo_only",
        "test_file": "temporary regression test: zero-value payment",
        "before": before,
        "after": after,
        "message": "The patch was applied only to a temporary copy of the bundled demo source.",
    }


def _run_pytest(root: Path, test_file: Path) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-q"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout + result.stderr
    passed, failed = 0, 0
    import re
    summary = re.search(r"(\d+) failed", output)
    if summary:
        failed = int(summary.group(1))
    summary = re.search(r"(\d+) passed", output)
    if summary:
        passed = int(summary.group(1))
    return {"passed": passed, "failed": failed, "output": output}
