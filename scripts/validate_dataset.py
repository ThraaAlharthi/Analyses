#!/usr/bin/env python3
"""Validate an instruction-tuning dataset (.jsonl).

  1. every line parses as valid JSON
  2. every example has instruction / input / output
  3. the `input` field itself parses as JSON
  4. no duplicate examples
  5. every number in `output` also appears in `input`
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REQUIRED = ("instruction", "input", "output")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, ln, msg):
        self.errors.append(f"  line {ln:>3}: {msg}")

    def warn(self, ln, msg):
        self.warnings.append(f"  line {ln:>3}: {msg}")


def classify(input_str, output):
    data = json.loads(input_str)
    if isinstance(data, dict) and len(data.get("observations", [])) >= 2:
        return "comparison"
    if output.lstrip().startswith(("لا يمكن", "البيانات", "تعذّر")):
        return "refusal"
    return "single_date"


def validate(path):
    report, seen, counts, total = Report(), {}, defaultdict(int), 0

    with path.open(encoding="utf-8") as fh:
        for ln, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            total += 1

            try:
                ex = json.loads(raw)
            except json.JSONDecodeError as e:
                report.error(ln, f"not valid JSON -- {e.msg} at col {e.colno}")
                continue
            if not isinstance(ex, dict):
                report.error(ln, f"expected an object, got {type(ex).__name__}")
                continue

            missing = [f for f in REQUIRED if f not in ex]
            if missing:
                report.error(ln, f"missing field(s): {', '.join(missing)}")
                continue
            blank = [f for f in REQUIRED if not str(ex[f]).strip()]
            if blank:
                report.error(ln, f"empty field(s): {', '.join(blank)}")
                continue

            instruction, input_str, output = ex["instruction"], ex["input"], ex["output"]
            if not isinstance(input_str, str):
                report.error(ln, "`input` must be a JSON string, not a nested object")
                continue

            try:
                json.loads(input_str)
            except json.JSONDecodeError as e:
                report.error(ln, f"`input` is not valid JSON -- {e.msg}")
                continue

            fp = f"{instruction}|{input_str}|{output}"
            if fp in seen:
                report.error(ln, f"duplicate of line {seen[fp]}")
                continue
            seen[fp] = ln

            stray = [t for t in NUMBER_RE.findall(output) if t not in input_str]
            if stray:
                report.error(ln, "output contains number(s) absent from input: "
                                 + ", ".join(sorted(set(stray))))

            if any(c in output for c in ARABIC_INDIC):
                report.warn(ln, "output uses Arabic-Indic digits; number check cannot see them")

            counts[classify(input_str, output)] += 1

    return report, total, counts


def main():
    ap = argparse.ArgumentParser(description="Validate an instruction .jsonl dataset.")
    ap.add_argument("path", type=Path, nargs="?", default=Path("data/instructions.jsonl"))
    args = ap.parse_args()

    if not args.path.is_file():
        print(f"no such file: {args.path}", file=sys.stderr)
        return 1

    report, total, counts = validate(args.path)

    print(f"\n{args.path}  --  {total} example(s)\n")
    print("  coverage:")
    for b in ("single_date", "comparison", "refusal"):
        print(f"    {b:<12} {counts.get(b, 0):>3}")

    if report.warnings:
        print(f"\n{len(report.warnings)} warning(s):")
        print("\n".join(report.warnings))

    if report.errors:
        print(f"\n{len(report.errors)} error(s):")
        print("\n".join(report.errors))
        print()
        return 1

    short = []
    if counts.get("refusal", 0) < 5:
        short.append(f"need >=5 refusals, have {counts.get('refusal', 0)}")
    if counts.get("comparison", 0) < 5:
        short.append(f"need >=5 comparisons, have {counts.get('comparison', 0)}")
    if total < 60:
        short.append(f"need >=60 examples, have {total}")

    if short:
        print("\nstructurally valid, but short of target:")
        for s in short:
            print(f"    - {s}")
        print()
        return 0

    print("\nall checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
