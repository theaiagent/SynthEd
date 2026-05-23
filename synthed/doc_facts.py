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

_INVENTORY_BEGIN = "<!-- BEGIN:test_inventory -->"
_INVENTORY_END = "<!-- END:test_inventory -->"


@dataclass(frozen=True)
class DocFacts:
    test_count: int
    test_file_count: int
    sobol_param_count: int


def _parametrize_cardinality(func: ast.FunctionDef) -> int:
    """Return the number of pytest collections produced by *func*.

    pytest expands `@pytest.mark.parametrize("name", [...])` into one collected
    test per element of the list/tuple, so a literal ast.FunctionDef count
    undercounts parametrized tests. Recognises the common literal form; falls
    back to 1 when the argument is dynamic (preserves prior behaviour).
    """
    cardinality = 1
    for deco in func.decorator_list:
        # Match pytest.mark.parametrize(...) call (any depth of attribute access).
        if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                and deco.func.attr == "parametrize"):
            continue
        # parametrize(argname, argvalues, ...): argvalues is positional arg index 1
        if len(deco.args) < 2:
            continue
        argvalues = deco.args[1]
        if isinstance(argvalues, (ast.List, ast.Tuple)):
            cardinality *= max(1, len(argvalues.elts))
    return cardinality


def _extract_module_docstring(tree: ast.Module) -> str:
    """Extract the module-level docstring from an AST, or return '\u2014'."""
    if (tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        # Take first line, strip surrounding whitespace
        doc = tree.body[0].value.value.strip()
        # Remove common prefixes like "Tests for ..." to keep coverage column concise
        for prefix in ("Tests for ", "Test for ", "Integration tests: ",
                       "Integration tests for the ", "Integration tests for ",
                       "Structural tests for ", "Targeted tests to ",
                       "Accessibility regression guards for the ",
                       "Engine integration tests for "):
            if doc.startswith(prefix):
                doc = doc[len(prefix):]
                break
        # Remove trailing period
        doc = doc.rstrip(".")
        # Truncate at first newline (multi-line docstrings)
        doc = doc.split("\n")[0].strip()
        return doc
    return "\u2014"


def _count_file_tests(tree: ast.Module) -> int:
    """Count test functions in an AST, accounting for parametrize."""
    return sum(
        _parametrize_cardinality(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )


def collect() -> DocFacts:
    tests_dir = _ROOT / "tests"
    test_files = sorted(tests_dir.glob("test_*.py"))
    test_count = 0
    for tf in test_files:
        tree = ast.parse(tf.read_text(encoding="utf-8"))
        test_count += _count_file_tests(tree)

    sobol_file = _ROOT / "synthed" / "analysis" / "sobol_sensitivity.py"
    sobol_text = sobol_file.read_text(encoding="utf-8")
    sobol_param_count = sobol_text.count("SobolParameter(")

    return DocFacts(
        test_count=test_count,
        test_file_count=len(test_files),
        sobol_param_count=sobol_param_count,
    )


def _collect_test_inventory() -> list[tuple[str, int, str]]:
    """Collect per-file test inventory: (filename, test_count, description).

    Sorted alphabetically by filename.
    """
    tests_dir = _ROOT / "tests"
    test_files = sorted(tests_dir.glob("test_*.py"))
    inventory: list[tuple[str, int, str]] = []
    for tf in test_files:
        tree = ast.parse(tf.read_text(encoding="utf-8"))
        count = _count_file_tests(tree)
        description = _extract_module_docstring(tree)
        inventory.append((tf.name, count, description))
    return inventory


def _generate_inventory_table(inventory: list[tuple[str, int, str]]) -> str:
    """Generate a markdown table from the test inventory."""
    lines = [
        "| Test File | Tests | Coverage |",
        "|-----------|-------|----------|",
    ]
    for filename, count, description in inventory:
        lines.append(f"| `{filename}` | {count} | {description} |")
    return "\n".join(lines)


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
    expected: int | str
    found: int | str
    description: str


def _verify_inventory(problems: list[Discrepancy]) -> None:
    """Check that the THEORY.md test inventory table matches source."""
    theory_path = _ROOT / "docs" / "THEORY.md"
    if not theory_path.exists():
        return
    text = theory_path.read_text(encoding="utf-8")
    if _INVENTORY_BEGIN not in text or _INVENTORY_END not in text:
        problems.append(Discrepancy(
            "docs/THEORY.md", "test_inventory", "sentinels present",
            "sentinels missing", "Test inventory sentinel comments",
        ))
        return

    # Extract current table between sentinels
    begin_idx = text.index(_INVENTORY_BEGIN) + len(_INVENTORY_BEGIN)
    end_idx = text.index(_INVENTORY_END)
    current_table = text[begin_idx:end_idx].strip()

    # Generate expected table
    inventory = _collect_test_inventory()
    expected_table = _generate_inventory_table(inventory)

    if current_table != expected_table:
        problems.append(Discrepancy(
            "docs/THEORY.md", "test_inventory",
            f"{len(inventory)} files", "stale table",
            "Test inventory table content",
        ))


def _fix_inventory() -> bool:
    """Replace THEORY.md test inventory table between sentinels. Returns True if changed."""
    theory_path = _ROOT / "docs" / "THEORY.md"
    if not theory_path.exists():
        return False
    text = theory_path.read_text(encoding="utf-8")
    if _INVENTORY_BEGIN not in text or _INVENTORY_END not in text:
        return False

    inventory = _collect_test_inventory()
    new_table = _generate_inventory_table(inventory)

    begin_idx = text.index(_INVENTORY_BEGIN) + len(_INVENTORY_BEGIN)
    end_idx = text.index(_INVENTORY_END)

    new_text = text[:begin_idx] + "\n" + new_table + "\n" + text[end_idx:]
    if new_text != text:
        theory_path.write_text(new_text, encoding="utf-8")
        return True
    return False


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

    _verify_inventory(problems)
    return problems


def fix() -> list[str]:
    """Auto-fix stale numbers and inventory table. Returns list of fixed files."""
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

    # Fix test inventory table
    if _fix_inventory():
        if "docs/THEORY.md" not in fixed_files:
            fixed_files.append("docs/THEORY.md")

    return fixed_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify/fix documentation metrics")
    parser.add_argument("--fix", action="store_true", help="Auto-fix stale numbers")
    args = parser.parse_args()

    facts = collect()
    print(f"Tests:        {facts.test_count} across {facts.test_file_count} files")
    print(f"Sobol params: {facts.sobol_param_count}")

    # Show inventory summary
    inventory = _collect_test_inventory()
    print(f"Inventory:    {len(inventory)} test files with docstrings")
    missing_docs = [name for name, _, desc in inventory if desc == "\u2014"]
    if missing_docs:
        print(f"  Missing docstrings: {', '.join(missing_docs)}")
    print()

    if args.fix:
        fixed = fix()
        if fixed:
            print(f"FIXED {len(fixed)} file(s):")
            for f in fixed:
                print(f"  {f}")
        else:
            print("Nothing to fix \u2014 all docs consistent.")
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
