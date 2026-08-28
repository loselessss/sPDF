"""Run the test suite with Windows Qt GUI cases isolated by process."""

import ast
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"
DOCUMENT_WORKFLOW = TESTS / "test_document_workflow.py"


def _run(test_name):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(TESTS), env.get("PYTHONPATH", ""))))
    print("\n=== %s ===" % test_name, flush=True)
    return subprocess.run(
        [sys.executable, "-m", "unittest", test_name, "-v"],
        cwd=ROOT,
        env=env,
        check=False,
    ).returncode


def _document_window_tests():
    tree = ast.parse(DOCUMENT_WORKFLOW.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "DocumentWorkflowTests":
            return sorted(
                child.name for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name.startswith("test_"))
    raise RuntimeError("DocumentWorkflowTests was not found")


def main():
    test_names = []
    for path in sorted(TESTS.glob("test_*.py")):
        if path == DOCUMENT_WORKFLOW:
            test_names.extend(
                "test_document_workflow.DocumentWorkflowTests.%s" % method
                for method in _document_window_tests())
            test_names.append("test_document_workflow.RecoveryStoreTests")
        else:
            test_names.append(path.stem)

    for test_name in test_names:
        if _run(test_name):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
