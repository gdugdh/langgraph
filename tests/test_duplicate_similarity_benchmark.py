from __future__ import annotations

import json
import unittest

from duplicate_similarity_benchmark import ARTICLE_URL, build_samples, evaluate_algorithms


class DuplicateSimilarityBenchmarkTest(unittest.TestCase):
    def test_benchmark_metrics(self) -> None:
        samples = build_samples(seed=42, variants_per_cluster=10)
        results = evaluate_algorithms(samples)

        print("\nDuplicate similarity benchmark")
        print(f"Source article: {ARTICLE_URL}")
        print(json.dumps(results, ensure_ascii=False, indent=2))

        self.assertGreaterEqual(results["overlap_score"]["top1_accuracy"], 0.65)
        self.assertGreaterEqual(
            results["tfidf_char_wb_cosine"]["top1_accuracy"],
            results["overlap_score"]["top1_accuracy"],
        )
        self.assertGreaterEqual(
            results["tfidf_char_wb_cosine"]["best_f1"],
            results["overlap_score"]["best_f1"],
        )
        self.assertGreaterEqual(results["hashing_char_wb_cosine"]["recall_at_3"], 0.8)


if __name__ == "__main__":
    unittest.main()
