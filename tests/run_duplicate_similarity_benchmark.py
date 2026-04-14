from __future__ import annotations

import json
import sys
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from duplicate_similarity_benchmark import ARTICLE_URL, build_samples, evaluate_algorithms


def main() -> None:
    samples = build_samples(seed=42, variants_per_cluster=12)
    results = evaluate_algorithms(samples)

    print("Duplicate similarity benchmark")
    print(f"Source article: {ARTICLE_URL}")
    print(f"Samples: {len(samples)}")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
