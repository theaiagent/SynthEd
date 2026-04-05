"""Single source of truth for documentation-facing metrics.

Run as: python -m synthed.doc_facts
Exits 1 if any documentation file has stale numbers.

Use --fix to auto-update stale numbers in-place:
    python -m synthed.doc_facts --fix
"""
from __future__ import annotations

import argparse
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


@dataclass(frozen=True)
class DocCheck:
    """A pattern to verify in a documentation file."""
    file: str            # relative to _ROOT
    pattern: str         # regex with ONE capture group containing the number
    metric: str          # which DocFacts field to compare against
    description: str     # human-readable context


_DOC_CHECKS: list[DocCheck] = [
    # sobol_sensitivity.py header
    DocCheck(
        "synthed/analysis/sobol_sensitivity.py",
        r"Full parameter space:\s*(\d+)\s+parameters",
        "sobol_param_count",
        "Sobol header comment",
    ),
    DocCheck(
        "synthed/analysis/sobol_sensitivity.py",
        r"Default:\s*128\s*\*\s*\((\d+)\s*\+\s*2\)",
        "sobol_param_count",
        "Sobol sample size comment",
    ),
    # docs/THEORY.md
    DocCheck(
        "docs/THEORY.md",
        r"sobol_sensitivity\.py\s*#.*\((\d+)\s+params?\)",
        "sobol_param_count",
        "THEORY Sobol param count",
    ),
    DocCheck(
        "docs/THEORY.md",
        r"#\s*(\d+)\s+pytest\s+tests\s+across",
        "test_count",
        "THEORY test count (project structure)",
    ),
    DocCheck(
        "docs/THEORY.md",
        r"pytest\s+tests\s+across\s+(\d+)\s+files",
        "test_file_count",
        "THEORY test file count",
    ),
    DocCheck(
        "docs/THEORY.md",
        r"^(\d+)\s+pytest\s+tests",
        "test_count",
        "THEORY test suite heading",
    ),
    # .zenodo.json (HTML-encoded)
    DocCheck(
        ".zenodo.json",
        r"Sobol sensitivity analysis \((\d+) parameters\)",
        "sobol_param_count",
        "Zenodo Sobol param count",
    ),
]


@dataclass(frozen=True)
class Discrepancy:
    file: str
    metric: str
    expected: int
    found: int
    description: str


def verify() -> list[Discrepancy]:
    facts = collect()
    problems: list[Discrepancy] = []

    for check in _DOC_CHECKS:
        filepath = _ROOT / check.file
        if not filepath.exists():
            continue
        text = filepath.read_text(encoding="utf-8")
        for match in re.finditer(check.pattern, text, re.MULTILINE):
            found = int(match.group(1))
            expected = getattr(facts, check.metric)
            if found != expected:
                problems.append(Discrepancy(
                    check.file, check.metric, expected, found, check.description,
                ))

    return problems


def fix() -> list[str]:
    """Auto-fix stale numbers in documentation files. Returns list of fixed files."""
    facts = collect()
    fixed_files: list[str] = []

    for check in _DOC_CHECKS:
        filepath = _ROOT / check.file
        if not filepath.exists():
            continue
        text = filepath.read_text(encoding="utf-8")
        expected = getattr(facts, check.metric)

        def _replacer(m: re.Match) -> str:
            original = m.group(0)
            old_num = m.group(1)
            if int(old_num) == expected:
                return original
            return original.replace(old_num, str(expected), 1)

        new_text = re.sub(check.pattern, _replacer, text, flags=re.MULTILINE)
        if new_text != text:
            filepath.write_text(new_text, encoding="utf-8")
            if check.file not in fixed_files:
                fixed_files.append(check.file)

    return fixed_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify/fix documentation metrics")
    parser.add_argument("--fix", action="store_true", help="Auto-fix stale numbers")
    args = parser.parse_args()

    facts = collect()
    print(f"Tests:        {facts.test_count} across {facts.test_file_count} files")
    print(f"Sobol params: {facts.sobol_param_count}")
    print()

    if args.fix:
        fixed = fix()
        if fixed:
            print(f"FIXED {len(fixed)} file(s):")
            for f in fixed:
                print(f"  {f}")
        else:
            print("Nothing to fix — all docs consistent.")
        return

    problems = verify()
    if problems:
        print(f"STALE DOCS ({len(problems)} discrepancies):")
        for p in problems:
            print(f"  {p.file}: {p.description} says {p.found}, should be {p.expected}")
        print()
        print("Run with --fix to auto-update.")
        raise SystemExit(1)
    print("All docs consistent with source.")


if __name__ == "__main__":
    main()
