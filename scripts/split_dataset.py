#!/usr/bin/env python3
"""Splits a dataset .jsonl into train/val/test (80/10/10), holding out by
REGION (not by row) so no area appears in both train and eval -- otherwise
the model could just memorize a place name instead of generalizing.
"""
import json
import random
from pathlib import Path

SEED = 42
SOURCE = Path("data/instructions_real.jsonl")
OUT_DIR = Path("data")

def extract_region(input_str: str) -> str:
    data = json.loads(input_str)
    if "area_name_ar" in data:
        return data["area_name_ar"]
    if "observations" in data and data["observations"]:
        return data.get("area_name_ar", "__unknown__")
    return "__unknown__"

def main():
    random.seed(SEED)
    records = []
    with SOURCE.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            rec["_region"] = extract_region(rec["input"])
            records.append(rec)

    regions = sorted(set(r["_region"] for r in records))
    random.shuffle(regions)

    n = len(regions)
    n_train = max(1, int(n * 0.8))
    n_val = max(1, int(n * 0.1))
    train_regions = set(regions[:n_train])
    val_regions = set(regions[n_train:n_train + n_val])
    test_regions = set(regions[n_train + n_val:])

    splits = {"train": [], "val": [], "test": []}
    for r in records:
        reg = r["_region"]
        if reg in train_regions:
            splits["train"].append(r)
        elif reg in val_regions:
            splits["val"].append(r)
        else:
            splits["test"].append(r)

    for name, rows in splits.items():
        out_path = OUT_DIR / f"dataset_{name}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for r in rows:
                r.pop("_region", None)
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} examples -> {out_path}")

    print(f"\nregions -> train:{sorted(train_regions)}")
    print(f"regions -> val:{sorted(val_regions)}")
    print(f"regions -> test:{sorted(test_regions)}")

if __name__ == "__main__":
    main()
