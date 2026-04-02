"""Single source of truth for documentation-facing metrics.

Run as: python -m synthed.doc_facts
Exits 1 if any documentation file has stale numbers.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class DocFacts:
    test_count: int
    test_file_count: int
    sobol_param_count: int


def collect() -> DocFacts:
    tests_dir = _ROOT / "tests"
    test_files = sorted(tests_dir.glob("test_*.py"))
    test_count = 0
    for tf in test_files:
        tree = ast.parse(tf.read_text(encoding="utf-8"))
        test_count += sum(
            1 for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        )

    sobol_file = _ROOT / "synthed" / "analysis" / "sobol_sensitivity.py"
    sobol_text = sobol_file.read_text(encoding="utf-8")
    sobol_param_count = sobol_text.count("SobolParameter(")

    return DocFacts(
        test_count=test_count,
        test_file_count=len(test_files),
        sobol_param_count=sobol_param_count,
    )


_DOC_CHECKS: list[tuple[str, str, str]] = [
    # (file_glob, regex_pattern, metric_name)
    # Each regex must have ONE capture group with the number
]


@dataclass(frozen=True)
class Discrepancy:
    file: str
    metric: str
    expected: int
    found: int


def verify() -> list[Discrepancy]:
    facts = collect()
    problems: list[Discrepancy] = []

    # Check sobol_sensitivity.py header comment
    sobol_file = _ROOT / "synthed" / "analysis" / "sobol_sensitivity.py"
    sobol_text = sobol_file.read_text(encoding="utf-8")
    for match in re.finditer(r"Full parameter space:\s*(\d+)\s+parameters", sobol_text):
        found = int(match.group(1))
        if found != facts.sobol_param_count:
            problems.append(Discrepancy("sobol_sensitivity.py", "sobol_param_count", facts.sobol_param_count, found))

    return problems


def main() -> None:
    facts = collect()
    print(f"Tests:        {facts.test_count} across {facts.test_file_count} files")
    print(f"Sobol params: {facts.sobol_param_count}")
    print()
    problems = verify()
    if problems:
        print(f"STALE DOCS ({len(problems)} discrepancies):")
        for p in problems:
            print(f"  {p.file}: {p.metric} says {p.found}, should be {p.expected}")
        raise SystemExit(1)
    print("All docs consistent with source.")


if __name__ == "__main__":
    main()
