"""Regression tests for the pure decision rules of the benchmark runner.

Nothing here calls a model or reads the result database, and no case reads a
task fixture: the ones that need input files build them in a temporary
directory. The cases are the rules that a wrong answer would silently corrupt
a paid run: the overlay that pins a candidate, the candidate string grammar,
the rubric arithmetic and the inputs the judge is given, the judge stream
parse, long-context pricing, and which class wins a routing key.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest import mock


def load_bench_module():
    """Import `bench/bench.py` by path; it is a script, not an installed package."""
    path = Path(__file__).resolve().parents[1] / "bench.py"
    spec = importlib.util.spec_from_file_location("bench_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    # `dataclasses` resolves annotations through `sys.modules`, so the module
    # has to be registered before its body runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bench = load_bench_module()


class DottedOverlayTest(unittest.TestCase):
    def test_dotted_keys_become_nested_objects(self):
        self.assertEqual(
            bench.nest_dotted({"providers.cacheRetention": "long", "compaction.thresholdTokens": 150000}),
            {"providers": {"cacheRetention": "long"}, "compaction": {"thresholdTokens": 150000}},
        )

    def test_keys_sharing_a_prefix_merge(self):
        self.assertEqual(
            bench.nest_dotted({"task.agentModelOverrides.scout": "a", "task.agentModelOverrides.task": "b"}),
            {"task": {"agentModelOverrides": {"scout": "a", "task": "b"}}},
        )

    def test_empty_path_segment_is_rejected(self):
        with self.assertRaises(bench.BenchError):
            bench.nest_dotted({"providers..cacheRetention": "long"})

    def test_scalar_collision_is_rejected(self):
        with self.assertRaises(bench.BenchError):
            bench.nest_dotted({"providers": "long", "providers.cacheRetention": "long"})

    def test_overlay_pins_every_role_and_empties_the_fallback_chains(self):
        overlay = bench.candidate_overlay("openai-codex/gpt-5.6-luna:max", {})
        self.assertEqual(set(overlay["modelRoles"]), set(bench.MODEL_ROLES))
        self.assertEqual(
            set(overlay["task"]["agentModelOverrides"]),
            set(bench.AGENT_OVERRIDE_KEYS),
        )
        self.assertEqual(
            set(overlay["modelRoles"].values()) | set(overlay["task"]["agentModelOverrides"].values()),
            {"openai-codex/gpt-5.6-luna:max"},
        )
        self.assertEqual(overlay["retry"]["fallbackChains"], {})

    def test_variant_overrides_are_applied_over_the_pinned_base(self):
        overlay = bench.candidate_overlay(
            "openai-codex/gpt-5.6-luna:max",
            {"providers.cacheRetention": "long", "compaction.thresholdTokens": 150000},
        )
        self.assertEqual(overlay["providers"]["cacheRetention"], "long")
        self.assertEqual(overlay["compaction"]["thresholdTokens"], 150000)
        self.assertEqual(overlay["modelRoles"]["default"], "openai-codex/gpt-5.6-luna:max")

    def test_a_variant_may_not_move_a_pinned_path(self):
        for key in (
            "modelRoles",
            "modelRoles.smol",
            "task",
            "task.agentModelOverrides",
            "task.agentModelOverrides.scout",
            "retry.fallbackChains",
            "retry.fallbackChains.default",
        ):
            with self.subTest(key=key):
                with self.assertRaises(bench.BenchError):
                    bench.candidate_overlay("openai-codex/gpt-5.6-luna:max", {key: "x"})

    def test_a_variant_key_beside_a_pinned_path_is_allowed(self):
        overlay = bench.candidate_overlay("openai-codex/gpt-5.6-luna:max", {"retry.maxAttempts": 1})
        self.assertEqual(overlay["retry"]["maxAttempts"], 1)
        self.assertEqual(overlay["retry"]["fallbackChains"], {})


class CandidateStringTest(unittest.TestCase):
    def test_plain_selector_has_no_variant(self):
        self.assertEqual(bench.split_candidate("anthropic/claude-opus-5:high"), ("anthropic/claude-opus-5:high", ""))

    def test_variant_is_split_off_the_selector(self):
        self.assertEqual(
            bench.split_candidate("openai-codex/gpt-5.6-luna:max@cache-long"),
            ("openai-codex/gpt-5.6-luna:max", "cache-long"),
        )

    def test_empty_variant_is_rejected(self):
        with self.assertRaises(bench.BenchError):
            bench.split_candidate("openai-codex/gpt-5.6-luna:max@")

    def test_agy_candidate_rejects_a_variant(self):
        self.assertEqual(bench.split_candidate("agy/gemini-3.8-flash-high"), ("agy/gemini-3.8-flash-high", ""))
        with self.assertRaises(bench.BenchError):
            bench.split_candidate("agy/gemini-3.8-flash-high@cache-long")

    def test_unknown_variant_is_rejected_before_a_run_starts(self):
        config = {"candidates": ["anthropic/claude-opus-5:high"], "variants": {"cache-long": {"a.b": 1}}}
        self.assertEqual(
            bench.select_models(config, ["openai-codex/gpt-5.6-luna:max@cache-long"]),
            ["openai-codex/gpt-5.6-luna:max@cache-long"],
        )
        with self.assertRaises(bench.BenchError):
            bench.select_models(config, ["openai-codex/gpt-5.6-luna:max@compact-150k"])


class RubricScoreTest(unittest.TestCase):
    def test_score_is_the_sum_over_the_attainable_maximum(self):
        self.assertEqual(bench.rubric_quality_score((2, 2, 2), 3), 1.0)
        self.assertEqual(bench.rubric_quality_score((0, 0, 0), 3), 0.0)
        self.assertEqual(bench.rubric_quality_score((2, 1, 0), 3), 0.5)

    def test_zero_criteria_is_an_error(self):
        with self.assertRaises(bench.BenchError):
            bench.rubric_quality_score((), 0)

    def test_threshold_boundary_passes_on_equality(self):
        score = bench.rubric_quality_score((2, 2, 2, 2, 1), 5)  # 9/10
        self.assertEqual(score, 0.9)
        verdict = bench.JudgeResult(score, scores=(2, 2, 2, 2, 1), cost_total=0.01)
        self.assertTrue(bench.rubric_verdict_passed(verdict, 0.9))
        self.assertFalse(bench.rubric_verdict_passed(verdict, 0.95))

    def test_an_unusable_verdict_never_passes(self):
        parse_error = bench.JudgeResult(None, cost_total=0.01, parse_error=True)
        self.assertFalse(bench.rubric_verdict_passed(parse_error, bench.DEFAULT_PASS_THRESHOLD))
        missing_score = bench.JudgeResult(None)
        self.assertFalse(bench.rubric_verdict_passed(missing_score, bench.DEFAULT_PASS_THRESHOLD))

    def test_a_missing_deliverable_scores_zero_without_calling_a_judge(self):
        verdict = bench.JudgeResult(0.0, rationale="the candidate wrote no report.md", invoked=False)
        self.assertFalse(bench.rubric_verdict_passed(verdict, bench.DEFAULT_PASS_THRESHOLD))
        self.assertFalse(verdict.invoked)
        self.assertEqual(verdict.cost_total, 0.0)


class RubricContextTest(unittest.TestCase):
    """`rubric.context` carries fixture inputs the judge cannot open itself."""

    def rubric(self, context: list[str]) -> dict:
        return {
            "output": "report.md",
            "reference": "classes.json",
            "criteria": ["형식", "입력 충실도"],
            "context": context,
        }

    def test_a_context_path_that_is_not_a_fixture_relative_file_fails_to_load(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture"
            fixture.mkdir()
            (fixture / "input.txt").write_text("ORIGINAL INPUT", encoding="utf-8")
            (fixture / "nested").mkdir()
            bad_paths = (
                ["missing.txt"],
                ["../input.txt"],
                ["/etc/hostname"],
                ["nested"],
                # Absolute even though it lands inside the fixture.
                [str(fixture / "input.txt")],
            )
            for bad in bad_paths:
                with self.subTest(context=bad), self.assertRaises(bench.BenchError):
                    bench.parse_rubric(self.rubric(bad), Path("task.json"), fixture)
            parsed = bench.parse_rubric(self.rubric(["input.txt"]), Path("task.json"), fixture)
        self.assertEqual(parsed.context, ("input.txt",))

    def test_grading_sends_the_original_fixture_file_ahead_of_the_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            fixture.mkdir()
            (fixture / "input.txt").write_text("ORIGINAL INPUT", encoding="utf-8")
            reference = root / "reference.md"
            reference.write_text("REFERENCE", encoding="utf-8")
            work = root / "work"
            work.mkdir()
            # The candidate's copy of the same input says something else, and
            # its own deliverable must not be mistaken for the input either.
            (work / "input.txt").write_text("EDITED BY THE CANDIDATE", encoding="utf-8")
            (work / "report.md").write_text("CANDIDATE", encoding="utf-8")
            task = bench.TaskDefinition(
                task_id="rubric-context",
                title="T",
                task_class="docs-business",
                fixture=fixture,
                prompt="작업",
                verify=("true",),
                timeout_seconds=1,
                default_repetitions=1,
                estimated_usage={},
                protected_paths=(),
                rubric=bench.RubricDefinition(
                    output="report.md",
                    reference=reference,
                    criteria=("입력 충실도",),
                    pass_threshold=0.7,
                    context=("input.txt",),
                ),
            )
            calls: list[tuple] = []

            def fake_judge(prompt, criteria, reference_text, candidate_text, judge_selector, context=()):
                calls.append((prompt, criteria, reference_text, candidate_text, judge_selector, context))
                return bench.JudgeResult(1.0)

            with mock.patch.object(bench, "judge", fake_judge):
                result = bench.grade_rubric(task, work, "anthropic/claude-opus-5:high")

        self.assertEqual(result.quality_score, 1.0)
        self.assertEqual(len(calls), 1)
        prompt, criteria, reference_text, candidate_text, selector, context = calls[0]
        self.assertEqual(context, [("input.txt", "ORIGINAL INPUT")])
        assembled = bench.judge_prompt(prompt, criteria, reference_text, candidate_text, context)
        self.assertIn("## 입력 자료: input.txt", assembled)
        self.assertIn("ORIGINAL INPUT", assembled)
        self.assertNotIn("EDITED BY THE CANDIDATE", assembled)
        self.assertLess(
            assembled.index("## 입력 자료: input.txt"), assembled.index("=== REFERENCE DELIVERABLE ===")
        )

    def test_no_context_leaves_the_prompt_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            parsed = bench.parse_rubric(self.rubric([]), Path("task.json"), Path(directory))
        self.assertEqual(parsed.context, ())
        self.assertNotIn("입력 자료", bench.judge_prompt("작업", parsed.criteria, "REF", "CAND"))


class JudgeStreamTest(unittest.TestCase):
    def stream(self, *events: dict) -> str:
        return "\n".join(json.dumps(event) for event in events) + "\n"

    def message_end(self, text: str, cost: float) -> dict:
        return {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
                "usage": {"input": 10, "output": 2, "cost": {"total": cost}},
            },
        }

    def test_last_message_end_supplies_the_text_and_the_cost(self):
        stream = self.stream(
            {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "ignored"}},
            self.message_end('{"scores": [2, 1], "rationale": "first"}', 0.001),
            self.message_end('{"scores": [1, 1], "rationale": "final"}', 0.002),
            {"type": "turn_end"},
        )
        text, cost = bench.judge_stream_payload(stream)
        self.assertEqual(text, '{"scores": [1, 1], "rationale": "final"}')
        self.assertEqual(cost, 0.002)
        self.assertEqual(bench.parse_judge_verdict(text, 2), ((1, 1), "final"))

    def test_thinking_blocks_are_dropped_from_the_text(self):
        event = self.message_end('{"scores": [0, 2], "rationale": "ok"}', 0.5)
        event["message"]["content"].insert(0, {"type": "thinking", "thinking": "deliberating"})
        text, cost = bench.judge_stream_payload(self.stream(event))
        self.assertEqual(text, '{"scores": [0, 2], "rationale": "ok"}')
        self.assertEqual(cost, 0.5)
        self.assertEqual(bench.parse_judge_verdict(text, 2), ((0, 2), "ok"))

    def test_a_verdict_wrapped_in_prose_or_a_code_fence_is_rejected(self):
        verdict = '{"scores": [0, 2], "rationale": "ok"}'
        self.assertIsNone(bench.parse_judge_verdict(f"here you go:\n{verdict}", 2))
        self.assertIsNone(bench.parse_judge_verdict(f"```json\n{verdict}\n```", 2))
        self.assertEqual(bench.parse_judge_verdict(f"\n  {verdict}\n", 2), ((0, 2), "ok"))

    def test_a_stream_without_a_message_end_yields_nothing(self):
        text, cost = bench.judge_stream_payload(self.stream({"type": "turn_end"}) + "not json\n")
        self.assertEqual(text, "")
        self.assertEqual(cost, 0.0)
        self.assertIsNone(bench.parse_judge_verdict(text, 2))

    def test_cost_survives_a_verdict_that_cannot_be_parsed(self):
        text, cost = bench.judge_stream_payload(self.stream(self.message_end("I cannot grade this.", 0.25)))
        self.assertEqual(cost, 0.25)
        self.assertIsNone(bench.parse_judge_verdict(text, 2))

    def test_wrong_score_count_and_out_of_range_scores_are_rejected(self):
        self.assertIsNone(bench.parse_judge_verdict('{"scores": [2, 2, 2]}', 2))
        self.assertIsNone(bench.parse_judge_verdict('{"scores": [2, 3]}', 2))
        self.assertIsNone(bench.parse_judge_verdict('{"scores": [2, -1]}', 2))
        self.assertIsNone(bench.parse_judge_verdict('{"scores": [2, 1.5]}', 2))
        self.assertIsNone(bench.parse_judge_verdict('{"scores": [2, true]}', 2))
        self.assertIsNone(bench.parse_judge_verdict('{"rationale": "no scores"}', 2))
        self.assertEqual(bench.parse_judge_verdict('{"scores": [2, 0]}', 2), ((2, 0), ""))


class LongContextCostTest(unittest.TestCase):
    def rate(self) -> "bench.ModelRate":
        return bench.ModelRate(
            base={"input": 4.0, "output": 20.0, "cacheRead": 0.4, "cacheWrite": 5.0},
            long_context={"input": 10.0, "output": 45.0, "cacheRead": 1.0, "cacheWrite": 12.5},
            long_context_threshold=272_000,
        )

    def test_a_request_below_the_threshold_uses_the_base_band(self):
        usage = {"input": 100_000, "output": 1_000, "cacheRead": 0, "cacheWrite": 0}
        self.assertFalse(self.rate().is_long_context(bench.context_tokens(usage)))
        self.assertAlmostEqual(self.rate().cost(usage), (100_000 * 4.0 + 1_000 * 20.0) / 1_000_000)

    def test_the_cached_prefix_counts_toward_the_threshold(self):
        usage = {"input": 100_000, "output": 1_000, "cacheRead": 180_000, "cacheWrite": 0}
        self.assertTrue(self.rate().is_long_context(bench.context_tokens(usage)))
        self.assertAlmostEqual(
            self.rate().cost(usage),
            (100_000 * 10.0 + 1_000 * 45.0 + 180_000 * 1.0) / 1_000_000,
        )

    def test_exactly_at_the_threshold_stays_on_the_base_band(self):
        usage = {"input": 272_000, "output": 0, "cacheRead": 0, "cacheWrite": 0}
        self.assertFalse(self.rate().is_long_context(bench.context_tokens(usage)))
        self.assertAlmostEqual(self.rate().cost(usage), 272_000 * 4.0 / 1_000_000)

    def test_a_model_without_a_long_context_band_never_switches(self):
        rate = bench.ModelRate(base={"input": 5.0, "output": 25.0, "cacheRead": 0.5, "cacheWrite": 6.25})
        usage = {"input": 900_000, "output": 0, "cacheRead": 0, "cacheWrite": 0}
        self.assertFalse(rate.is_long_context(bench.context_tokens(usage)))
        self.assertAlmostEqual(rate.cost(usage), 900_000 * 5.0 / 1_000_000)

    def test_a_malformed_catalog_band_is_ignored(self):
        self.assertEqual(
            bench.long_context_band({"inputThreshold": 272_000, "input": 10.0}),
            {"long_context": None, "long_context_threshold": None},
        )
        self.assertEqual(
            bench.long_context_band(None),
            {"long_context": None, "long_context_threshold": None},
        )


class RoutingConflictTest(unittest.TestCase):
    def classes(self) -> dict:
        return {
            "dev-feature": bench.TaskClass("dev-feature", "기능", 0.5, "verify", ("default",), ("task",)),
            "dev-fix": bench.TaskClass("dev-fix", "수정", 0.3, "verify", ("default",), ("task",)),
            "research": bench.TaskClass("research", "조사", 0.2, "verify", ("smol",), ("scout",)),
        }

    def entry(
        self,
        class_id: str,
        weight: float,
        recommended: str,
        low_sample: bool = False,
        candidates: Sequence[Mapping[str, Any]] = (),
        subagent_observed: bool = True,
    ) -> dict:
        # Every recorded winner has a summary in its own class, so an entry
        # without an explicit candidate list gets the one its winner implies.
        summaries = list(candidates) or [self.candidate(recommended, 1.0, 0.01, low_sample=low_sample)]
        return {
            "class": class_id,
            "weight": weight,
            "recommended": recommended,
            "low_sample": low_sample,
            "candidates": summaries,
            "harness_roles": [],
            "agent_overrides": [],
            "subagent_observed": subagent_observed,
        }

    def candidate(
        self,
        name: str,
        pass_rate: float,
        actual_per_task: float,
        low_sample: bool = False,
        attempts: int = 5,
        self_judge: bool | None = None,
    ) -> dict:
        return {
            "candidate": name,
            "pass_rate": pass_rate,
            "actual_per_task": actual_per_task,
            "low_sample": low_sample,
            "attempts": attempts,
            "self_judge": self_judge,
        }

    def test_the_heavier_class_keeps_a_contested_role(self):
        routing = bench.routing_recommendation(
            [
                self.entry("dev-fix", 0.3, "openai-codex/gpt-5.6-luna:max"),
                self.entry("dev-feature", 0.5, "anthropic/claude-opus-5:high"),
                self.entry("research", 0.2, "openai-codex/gpt-5.6-luna:xhigh"),
            ],
            self.classes(),
        )
        self.assertEqual(
            routing["modelRoles"],
            {"default": "anthropic/claude-opus-5:high", "smol": "openai-codex/gpt-5.6-luna:xhigh"},
        )
        self.assertEqual(
            routing["agentModelOverrides"],
            {"task": "anthropic/claude-opus-5:high", "scout": "openai-codex/gpt-5.6-luna:xhigh"},
        )
        self.assertEqual(
            [(item["key"], item["winner"]["class"], item["loser"]["class"]) for item in routing["conflicts"]],
            [
                ("modelRoles.default", "dev-feature", "dev-fix"),
                ("task.agentModelOverrides.task", "dev-feature", "dev-fix"),
            ],
        )

    def test_agreement_on_the_same_candidate_is_not_a_conflict(self):
        routing = bench.routing_recommendation(
            [
                self.entry("dev-feature", 0.5, "anthropic/claude-opus-5:high"),
                self.entry("dev-fix", 0.3, "anthropic/claude-opus-5:high"),
            ],
            self.classes(),
        )
        self.assertEqual(routing["conflicts"], [])
        self.assertEqual(routing["modelRoles"], {"default": "anthropic/claude-opus-5:high"})

    def test_a_variant_winner_contributes_only_its_selector_to_the_role_map(self):
        routing = bench.routing_recommendation(
            [self.entry("dev-feature", 0.5, "openai-codex/gpt-5.6-luna:max@cache-long", low_sample=True)],
            self.classes(),
        )
        self.assertEqual(routing["modelRoles"], {"default": "openai-codex/gpt-5.6-luna:max"})
        self.assertEqual(routing["variants"], {"dev-feature": "cache-long"})
        self.assertEqual(routing["low_sample"], ["dev-feature"])
        self.assertEqual(routing["unroutable"], [])

    def test_an_agy_winner_is_replaced_by_the_best_omp_candidate_of_its_class(self):
        routing = bench.routing_recommendation(
            [
                self.entry(
                    "research",
                    0.2,
                    "agy/gemini-3.8-flash-high",
                    candidates=[
                        self.candidate("agy/gemini-3.8-flash-high", 1.0, 0.0),
                        self.candidate("openai-codex/gpt-5.6-luna:max@cache-long", 1.0, 0.01),
                        self.candidate("anthropic/claude-opus-5:high", 1.0, 0.2),
                        self.candidate("openai-codex/gpt-5.6-sol:max", 0.5, 0.001),
                    ],
                )
            ],
            self.classes(),
        )
        self.assertEqual(routing["modelRoles"], {"smol": "openai-codex/gpt-5.6-luna:max"})
        self.assertEqual(routing["agentModelOverrides"], {"scout": "openai-codex/gpt-5.6-luna:max"})
        self.assertEqual(routing["variants"], {"research": "cache-long"})
        self.assertEqual(
            [(item["key"], item["class"], item["candidate"], item["omp_fallback"]) for item in routing["unroutable"]],
            [
                ("modelRoles.smol", "research", "agy/gemini-3.8-flash-high", "openai-codex/gpt-5.6-luna:max@cache-long"),
                (
                    "task.agentModelOverrides.scout",
                    "research",
                    "agy/gemini-3.8-flash-high",
                    "openai-codex/gpt-5.6-luna:max@cache-long",
                ),
            ],
        )

    def test_an_agy_winner_with_no_omp_sibling_leaves_the_role_empty(self):
        routing = bench.routing_recommendation(
            [
                self.entry(
                    "research",
                    0.2,
                    "agy/gemini-3.8-flash-high",
                    candidates=[self.candidate("agy/gemini-3.8-flash-high", 1.0, 0.0)],
                )
            ],
            self.classes(),
        )
        self.assertEqual(routing["modelRoles"], {})
        self.assertEqual(routing["agentModelOverrides"], {})
        self.assertEqual([item["omp_fallback"] for item in routing["unroutable"]], [None, None])

    def test_an_agy_winner_still_blocks_a_lighter_class_from_the_role(self):
        routing = bench.routing_recommendation(
            [
                self.entry(
                    "dev-feature",
                    0.5,
                    "agy/gemini-3.8-flash-high",
                    candidates=[self.candidate("agy/gemini-3.8-flash-high", 1.0, 0.0)],
                ),
                self.entry("dev-fix", 0.3, "anthropic/claude-opus-5:high"),
            ],
            self.classes(),
        )
        self.assertEqual(routing["modelRoles"], {})
        self.assertEqual(
            [(item["key"], item["winner"]["class"], item["loser"]["class"]) for item in routing["conflicts"]],
            [
                ("modelRoles.default", "dev-feature", "dev-fix"),
                ("task.agentModelOverrides.task", "dev-feature", "dev-fix"),
            ],
        )


class SubagentObservationTest(unittest.TestCase):
    """Only a class that actually spawned a subagent may recommend its keys."""

    def classes(self) -> dict:
        return {
            "dev-feature": bench.TaskClass("dev-feature", "기능", 0.6, "verify", ("default", "mid"), ("task",)),
            "dev-test-ci": bench.TaskClass("dev-test-ci", "테스트", 0.4, "verify", ("default", "mid"), ("task",)),
        }

    def entry(
        self,
        class_id: str,
        weight: float,
        recommended: str | None,
        subagent_observed: bool,
        attempts: int = 5,
    ) -> dict:
        candidates = []
        if recommended:
            candidates.append(
                {
                    "candidate": recommended,
                    "pass_rate": 1.0,
                    "actual_per_task": 0.01,
                    "low_sample": False,
                    "attempts": attempts,
                    "self_judge": None,
                }
            )
        return {
            "class": class_id,
            "weight": weight,
            "recommended": recommended,
            "low_sample": False,
            "candidates": candidates,
            "harness_roles": [],
            "agent_overrides": [],
            "subagent_observed": subagent_observed,
        }

    def test_a_class_with_no_subagent_run_recommends_only_the_main_role(self):
        routing = bench.routing_recommendation(
            [self.entry("dev-feature", 0.6, "openai-codex/gpt-5.6-luna:max", False)], self.classes()
        )
        self.assertEqual(routing["modelRoles"], {"default": "openai-codex/gpt-5.6-luna:max"})
        self.assertEqual(routing["agentModelOverrides"], {})
        self.assertEqual(
            [(item["key"], item["class"]) for item in routing["unobserved"]],
            [("modelRoles.mid", "dev-feature"), ("task.agentModelOverrides.task", "dev-feature")],
        )
        self.assertEqual(sorted(routing["evidence"]), ["modelRoles.default"])

    def test_an_unobserved_key_is_left_to_a_lighter_class_that_did_observe_one(self):
        routing = bench.routing_recommendation(
            [
                self.entry("dev-feature", 0.6, "openai-codex/gpt-5.6-luna:max", False),
                self.entry("dev-test-ci", 0.4, "openai-codex/gpt-5.6-sol:max", True, attempts=7),
            ],
            self.classes(),
        )
        self.assertEqual(
            routing["modelRoles"],
            {"default": "openai-codex/gpt-5.6-luna:max", "mid": "openai-codex/gpt-5.6-sol:max"},
        )
        self.assertEqual(routing["agentModelOverrides"], {"task": "openai-codex/gpt-5.6-sol:max"})
        self.assertEqual(routing["evidence"]["modelRoles.mid"]["class"], "dev-test-ci")
        self.assertEqual(routing["evidence"]["modelRoles.mid"]["samples"], 7)
        # The heavier class measured `modelRoles.default` and keeps owning it.
        self.assertEqual([item["key"] for item in routing["conflicts"]], ["modelRoles.default"])

    def test_a_class_with_no_recorded_run_still_reports_its_subagent_keys(self):
        routing = bench.routing_recommendation(
            [
                self.entry("dev-feature", 0.6, None, False),
                self.entry("dev-test-ci", 0.4, None, False),
            ],
            self.classes(),
        )
        self.assertEqual(routing["modelRoles"], {})
        self.assertEqual(routing["evidence"], {})
        self.assertEqual(
            [(item["key"], item["class"]) for item in routing["unobserved"]],
            [
                ("modelRoles.mid", "dev-feature"),
                ("task.agentModelOverrides.task", "dev-feature"),
                ("modelRoles.mid", "dev-test-ci"),
                ("task.agentModelOverrides.task", "dev-test-ci"),
            ],
        )


class ApplyProposalTest(unittest.TestCase):
    """The proposal is a partial update of apply.sh's two managed records."""

    def current(self) -> dict:
        return {
            "modelRoles": {"default": "a/b:high", "mid": "c/d:max", "smol": "e/f:max", "slow": "g/h:max"},
            "task.agentModelOverrides": {"task": "@mid", "scout": "@smol", "reviewer": "@slow"},
        }

    def routing(self, model_roles: dict, agent_overrides: dict, evidence: dict | None = None) -> dict:
        return {
            "modelRoles": model_roles,
            "agentModelOverrides": agent_overrides,
            "conflicts": [],
            "low_sample": [],
            "variants": {},
            "unroutable": [],
            "unobserved": [],
            "evidence": evidence or {},
        }

    def evidence(self, class_id: str, samples: int, variant: str = "") -> dict:
        return {
            "class": class_id,
            "candidate": "c/d:max",
            "selector": "c/d:max",
            "samples": samples,
            "self_judge": False,
            "variant": variant,
            "low_sample": False,
        }

    def test_a_key_with_no_recommendation_keeps_its_managed_value(self):
        proposal = bench.routing_proposal(self.current(), self.routing({"default": "x/y:max"}, {}))
        self.assertEqual(
            proposal["modelRoles"],
            {"default": "x/y:max", "mid": "c/d:max", "smol": "e/f:max", "slow": "g/h:max"},
        )
        self.assertEqual(proposal["task.agentModelOverrides"], self.current()["task.agentModelOverrides"])

    def test_an_override_keeps_its_alias_when_the_recommendation_is_that_role(self):
        routing = self.routing({"mid": "c/d:max"}, {"task": "c/d:max"})
        proposal = bench.routing_proposal(self.current(), routing)
        self.assertEqual(proposal["task.agentModelOverrides"]["task"], "@mid")
        self.assertEqual(bench.routing_changes(self.current(), proposal, routing, {}), [])

    def test_an_override_takes_the_selector_when_it_differs_from_its_role(self):
        routing = self.routing({"mid": "c/d:max"}, {"task": "x/y:max"})
        proposal = bench.routing_proposal(self.current(), routing)
        self.assertEqual(proposal["task.agentModelOverrides"]["task"], "x/y:max")
        self.assertEqual(
            [
                (item["key"], item["from"], item["to"])
                for item in bench.routing_changes(self.current(), proposal, routing, {})
            ],
            [("task.agentModelOverrides.task", "@mid", "x/y:max")],
        )

    def test_an_unchanged_value_is_reported_when_its_candidate_carried_a_variant(self):
        routing = self.routing(
            {"mid": "c/d:max"},
            {},
            evidence={"modelRoles.mid": self.evidence("dev-feature", 6, variant="cache-long")},
        )
        proposal = bench.routing_proposal(self.current(), routing)
        self.assertEqual(proposal["modelRoles"]["mid"], "c/d:max")
        changes = bench.routing_changes(
            self.current(), proposal, routing, {"cache-long": {"providers.cacheRetention": "long"}}
        )
        self.assertEqual(
            changes,
            [
                {
                    "key": "modelRoles.mid",
                    "from": "c/d:max",
                    "to": "c/d:max",
                    "class": "dev-feature",
                    "samples": 6,
                    "flags": ["variant:cache-long"],
                    "variant_overlay": {"providers.cacheRetention": "long"},
                }
            ],
        )


class ApplyRewriteTest(unittest.TestCase):
    """`--write` may only change apply.sh's two managed rows, byte for byte."""

    def test_rewriting_the_same_values_reproduces_the_file(self):
        script = bench.load_apply_script(bench.APPLY_SCRIPT)
        self.assertEqual(bench.rewrite_apply_script(script, script.values), b"".join(script.lines))

    def test_only_the_two_managed_rows_change_in_a_file_with_mixed_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "config.apply.sh"
            # Every second row gets CRLF, so a rewrite that normalized line
            # endings or re-encoded the file would show up as a byte change on
            # rows this command must not touch.
            original = [
                line + b"\r\n" if index % 2 else line + b"\n"
                for index, line in enumerate(bench.APPLY_SCRIPT.read_bytes().split(b"\n")[:-1])
            ]
            copy.write_bytes(b"".join(original))
            script = bench.load_apply_script(copy)
            updated = bench.rewrite_apply_script(
                script,
                {
                    "modelRoles": dict(script.values["modelRoles"], default="x/y:max"),
                    "task.agentModelOverrides": dict(script.values["task.agentModelOverrides"], task="x/y:max"),
                },
            )
            self.assertEqual(
                bench.changed_line_numbers(script, updated),
                sorted(index + 1 for index in script.rows.values()),
            )
            bench.write_apply_script(script, updated)
            after = copy.read_bytes().splitlines(keepends=True)
        self.assertEqual(len(after), len(original))
        self.assertEqual(
            [index for index, line in enumerate(after) if line != original[index]],
            sorted(script.rows.values()),
        )
        for setting in ("modelRoles", "task.agentModelOverrides"):
            row = after[script.rows[setting]]
            self.assertEqual(row.endswith(b"\r\n"), original[script.rows[setting]].endswith(b"\r\n"))
            self.assertIn(b'"x/y:max"', row)


class ApplyCheckTest(unittest.TestCase):
    """The check mode reports with 0 or 1; anything else is a failed check."""

    def script(self, directory: str, body: str) -> Path:
        path = Path(directory) / "fake-apply.sh"
        path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
        return path

    def test_a_reported_difference_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.script(directory, 'echo "different: modelRoles"\nexit 1')
            completed = bench.run_apply_check(path)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("different: modelRoles", completed.stdout)
        self.assertEqual(bench.apply_check_error(completed, path), "")

    def test_any_other_exit_code_fails_the_command(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.script(directory, 'echo "error: omp is not on PATH" >&2\nexit 2')
            completed = bench.run_apply_check(path)
            message = bench.apply_check_error(completed, path)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("exit 2", message)
        self.assertIn("omp is not on PATH", message)


class ClassWinnerTest(unittest.TestCase):
    def candidate(self, name: str, pass_rate: float, actual_per_task: float) -> dict:
        return {"candidate": name, "pass_rate": pass_rate, "actual_per_task": actual_per_task}

    def test_the_omp_only_pool_is_ranked_by_the_same_rule(self):
        pool = [
            self.candidate("agy/gemini-3.8-flash-high", 1.0, 0.0),
            self.candidate("openai-codex/gpt-5.6-luna:max", 1.0, 0.01),
        ]
        self.assertEqual(bench.pick_class_winner(pool)["candidate"], "agy/gemini-3.8-flash-high")
        omp_only = [item for item in pool if not bench.is_agy_candidate(item["candidate"])]
        self.assertEqual(bench.pick_class_winner(omp_only)["candidate"], "openai-codex/gpt-5.6-luna:max")
        self.assertIsNone(bench.pick_class_winner([]))

    def test_pass_rate_outranks_cost(self):
        winner = bench.pick_class_winner(
            [self.candidate("cheap", 0.5, 0.001), self.candidate("good", 0.9, 0.5)]
        )
        self.assertEqual(winner["candidate"], "good")

    def test_a_tie_on_pass_rate_is_broken_by_actual_cost(self):
        winner = bench.pick_class_winner(
            [self.candidate("expensive", 1.0, 0.5), self.candidate("cheap", 1.0, 0.01)]
        )
        self.assertEqual(winner["candidate"], "cheap")


class SchemaMigrationTest(unittest.TestCase):
    """A database written by the first runner must stay usable, in place."""

    OLD_SCHEMA = """
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            task_title TEXT NOT NULL,
            candidate TEXT NOT NULL,
            repeat_index INTEGER NOT NULL,
            passed INTEGER NOT NULL,
            protected_files_unchanged INTEGER NOT NULL,
            duration_seconds REAL NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cache_read_tokens INTEGER NOT NULL,
            cache_write_tokens INTEGER NOT NULL,
            cost_total REAL NOT NULL,
            catalog_cost_total REAL,
            request_count INTEGER NOT NULL,
            tool_call_count INTEGER NOT NULL,
            actual_model TEXT NOT NULL,
            actual_thinking TEXT NOT NULL,
            configured_matches_actual INTEGER NOT NULL,
            fallback_used INTEGER NOT NULL,
            observed_models_json TEXT NOT NULL,
            termination_reason TEXT NOT NULL,
            omp_exit_code INTEGER NOT NULL,
            verify_exit_code INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            session_file TEXT NOT NULL,
            session_files_json TEXT NOT NULL
        )
    """
    OLD_ROW = {
        "batch_id": "old-batch",
        "task_id": "bugfix-python",
        "task_title": "Python 경계 조건 버그 수정",
        "candidate": "openai-codex/gpt-5.6-luna:max",
        "repeat_index": 1,
        "passed": 1,
        "protected_files_unchanged": 1,
        "duration_seconds": 36.4,
        "input_tokens": 1000,
        "output_tokens": 50,
        "cache_read_tokens": 9000,
        "cache_write_tokens": 0,
        "cost_total": 0.006229,
        "catalog_cost_total": 0.006229,
        "request_count": 3,
        "tool_call_count": 4,
        "actual_model": "openai-codex/gpt-5.6-luna",
        "actual_thinking": "max",
        "configured_matches_actual": 1,
        "fallback_used": 0,
        "observed_models_json": "[]",
        "termination_reason": "completed",
        "omp_exit_code": 0,
        "verify_exit_code": 0,
        "created_at": "2026-09-01T00:00:00+00:00",
        "session_file": "/tmp/old/session.jsonl",
        "session_files_json": '["/tmp/old/session.jsonl"]',
    }

    def old_database(self) -> Path:
        directory = tempfile.mkdtemp(prefix="bench-migrate-test-")
        self.addCleanup(shutil.rmtree, directory, True)
        path = Path(directory) / "bench.db"
        columns = ", ".join(self.OLD_ROW)
        placeholders = ", ".join("?" for _ in self.OLD_ROW)
        with sqlite3.connect(path) as connection:
            connection.execute(self.OLD_SCHEMA)
            connection.execute(
                f"INSERT INTO runs ({columns}) VALUES ({placeholders})", tuple(self.OLD_ROW.values())
            )
        return path

    def columns(self, path: Path) -> set[str]:
        with sqlite3.connect(path) as connection:
            return {row[1] for row in connection.execute("PRAGMA table_info(runs)")}

    def test_initializing_an_old_database_migrates_it_instead_of_failing(self):
        path = self.old_database()
        bench.initialize_database(path)
        columns = self.columns(path)
        self.assertIn("agent_exit_code", columns)
        self.assertNotIn("omp_exit_code", columns)
        for added in (
            "task_class",
            "variant",
            "quality_score",
            "judge",
            "judge_cost_total",
            "cache_hit_ratio",
            "max_context_tokens",
            "long_context_requests",
            "subagent_request_count",
            "quota_bucket",
            "quota_fraction_used",
        ):
            self.assertIn(added, columns)
        with sqlite3.connect(path) as connection:
            indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertLessEqual({"runs_candidate_idx", "runs_task_idx", "runs_class_idx"}, indexes)

    def test_migration_keeps_the_recorded_row_and_leaves_new_columns_unset(self):
        path = self.old_database()
        bench.initialize_database(path)
        rows = bench.fetch_rows(path)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["candidate"], self.OLD_ROW["candidate"])
        self.assertEqual(row["agent_exit_code"], 0)
        self.assertEqual(row["task_class"], "")
        self.assertEqual(row["judge"], "")
        self.assertEqual(row["judge_cost_total"], 0)
        self.assertIsNone(row["quality_score"])
        self.assertIsNone(row["max_context_tokens"])

    def test_initializing_twice_is_a_no_op(self):
        path = self.old_database()
        bench.initialize_database(path)
        before = self.columns(path)
        bench.initialize_database(path)
        self.assertEqual(self.columns(path), before)
        self.assertEqual(len(bench.fetch_rows(path)), 1)


if __name__ == "__main__":
    unittest.main()


class ExternalTimeoutTest(unittest.TestCase):
    """An agent that outlives `--max-time` is one failed run, not an aborted batch."""

    def test_omp_timeout_is_recorded_as_a_failed_run(self):
        task = bench.TaskDefinition(
            task_id="t",
            title="t",
            task_class="dev-fix",
            fixture=Path("/nonexistent"),
            prompt="do it",
            verify=("true",),
            timeout_seconds=1,
            default_repetitions=1,
            estimated_usage={},
            protected_paths=(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / "session"
            session_dir.mkdir()

            def hang(command, **kwargs):
                raise subprocess.TimeoutExpired(command, kwargs["timeout"], output="partial")

            with mock.patch.object(bench.subprocess, "run", hang):
                completed, metrics = bench.run_omp(
                    task, "anthropic/claude-opus-5:high", Path(tmp), session_dir, {}, {}
                )
        self.assertEqual(completed.returncode, bench.EXTERNAL_TIMEOUT_EXIT)
        self.assertEqual(completed.stdout, "partial")
        self.assertTrue(metrics.termination_reason.startswith(bench.EXTERNAL_TIMEOUT))
