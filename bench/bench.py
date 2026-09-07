#!/usr/bin/env python3
"""Replay small coding tasks across agent candidates and report a Pareto frontier."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


BENCH_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
FACTS_FILE = ROOT / "docs" / "FACTS.md"
TASKS_DIR = BENCH_DIR / "tasks"
DEFAULT_CONFIG = BENCH_DIR / "config.json"
CLASSES_FILE = BENCH_DIR / "classes.json"
DEFAULT_DB = ROOT / "var" / "bench.db"
APPLY_SCRIPT = ROOT / "omp" / "config.apply.sh"
MODEL_DB = Path.home() / ".omp" / "agent" / "models.db"
TOKEN_KEYS = ("input", "output", "cacheRead", "cacheWrite")
CONTEXT_KEYS = ("input", "cacheRead", "cacheWrite")

# A task class is graded either by its `verify` command alone or by `verify`
# plus a rubric judge. `verify` is mandatory in both cases: it is the
# deterministic gate, and the judge only ranks quality above that gate.
GRADING_MODES = ("verify", "rubric")
DEFAULT_PASS_THRESHOLD = 0.7
JUDGE_PARSE_ERROR = "judge_parse_error"
JUDGE_TIMEOUT_SECONDS = 900
# The agent is given `--max-time`; if it still has not exited 45 seconds later the
# runner kills it and records the run as failed instead of aborting the batch.
EXTERNAL_TIMEOUT = "external_timeout"
EXTERNAL_TIMEOUT_EXIT = 124

# Every omp `modelRoles` key and every known `task.agentModelOverrides` key is
# pinned to the candidate under test. Pinning only `modelRoles.default` would
# let a subagent run on the user's own routing, and then the measurement is a
# mixture of two candidates instead of one. A variant may not touch these
# paths: the pin and the emptied fallback chain are what make a run one
# candidate's measurement, so a variant that moved them would be measuring
# something else under the candidate's name.
MODEL_ROLES = ("default", "slow", "mid", "smol", "tiny", "commit", "plan", "designer", "advisor")
AGENT_OVERRIDE_KEYS = ("scout", "librarian", "sonic", "task", "reviewer", "security-reviewer")
PINNED_OVERLAY_PATHS = (
    "modelRoles",
    "task.agentModelOverrides",
    "retry.fallbackChains",
    "retry.modelFallback",
    "retry.usageAwareFallback",
)
VARIANT_SEPARATOR = "@"

# `omp/config.apply.sh` carries each managed setting as one `<key>|<canonical
# JSON>` row of its heredoc. The routing proposal reads and rewrites exactly
# the two rows that hold the role map, and `--check` is that script's mode
# that only reports differing values without calling `omp config set`.
APPLY_ROLES_KEY = "modelRoles"
APPLY_OVERRIDES_KEY = "task.agentModelOverrides"
APPLY_SETTING_KEYS = (APPLY_ROLES_KEY, APPLY_OVERRIDES_KEY)
APPLY_CHECK_FLAG = "--check"
APPLY_CHECK_TIMEOUT_SECONDS = 600
# Exit codes of that mode which are a report rather than a failed check.
APPLY_CHECK_REPORT_CODES = (0, 1)
# An agent override may name a role instead of a selector, which is how
# apply.sh keeps an override following its role.
ROLE_ALIAS_PREFIX = "@"

# Only `modelRoles.default` is exercised by the agent the runner starts. Every
# other role and every `task.agentModelOverrides` key is reached only once a
# run spawns a subagent, so a class whose recorded runs never spawned one has
# measured nothing about those keys and must not recommend them.
MAIN_AGENT_ROLE = "default"

# Antigravity CLI candidates are written `agy/<model-id>`, with the model id
# exactly as `agy models` prints it. They carry no thinking suffix because the
# reasoning effort is already part of that id.
AGY_PROVIDER = "agy"
# `agy` bills no money: a run spends the Antigravity plan's quota instead. The
# runner records the weekly bucket it drew from, so quota stays a measurable
# axis even though the USD axis is zero.
AGY_QUOTA_BUCKETS = {"gemini": "gemini-weekly", "third-party": "3p-weekly"}
AGY_GEMINI_PREFIX = "gemini-"
AGY_CONVERSATIONS = Path.home() / ".gemini" / "antigravity-cli" / "conversations"

# A benchmark child inherits the user's discovered `APPEND_SYSTEM.md`, whose
# terminal decision gate makes a run block on a `herdr-hitl ask` whenever the
# resolved channel is `messenger`. That notifies a human per run and adds the
# wait to the measured elapsed time and cost. Channel resolution is no defence:
# an unattended benchmark is most likely to run exactly while the away marker
# is set. `--append-system-prompt` is the highest-precedence append input and a
# flag wins over every discovered file, so passing it suppresses that file.
# The value is multi-line so OMP uses it literally instead of trying to read it
# as a path. The rubric judge is called the same way for the same reason.
BENCH_APPEND_SYSTEM_PROMPT = """This is an automated benchmark run.
No human is reachable and no answer will ever arrive.
Never invoke `herdr-hitl`, and never ask for approval, confirmation, or a decision.
Never block on a human, a notification, or an interactive prompt.
Complete the assigned task and stop."""


class BenchError(RuntimeError):
    pass


@dataclass(frozen=True)
class TaskClass:
    class_id: str
    title: str
    weight: float
    grading: str
    harness_roles: tuple[str, ...]
    agent_overrides: tuple[str, ...]


@dataclass(frozen=True)
class RubricDefinition:
    output: str
    reference: Path
    criteria: tuple[str, ...]
    pass_threshold: float
    context: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    title: str
    task_class: str
    fixture: Path
    prompt: str
    verify: tuple[str, ...]
    timeout_seconds: int
    default_repetitions: int
    estimated_usage: dict[str, int]
    protected_paths: tuple[str, ...]
    rubric: RubricDefinition | None = None


@dataclass(frozen=True)
class ModelRate:
    base: dict[str, float]
    long_context: dict[str, float] | None = None
    long_context_threshold: int | None = None

    def is_long_context(self, context_tokens: int) -> bool:
        if self.long_context is None or self.long_context_threshold is None:
            return False
        return context_tokens > self.long_context_threshold

    def cost(self, usage: Mapping[str, int]) -> float:
        band = self.long_context if self.is_long_context(context_tokens(usage)) else self.base
        return cost_for_usage(usage, band)


@dataclass
class JudgeResult:
    quality_score: float | None
    scores: tuple[int, ...] = ()
    rationale: str = ""
    cost_total: float = 0.0
    parse_error: bool = False
    # False when the runner decided the outcome without paying a judge, so the
    # row records no judge at all.
    invoked: bool = True


@dataclass
class SessionMetrics:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_total: float = 0.0
    duration_seconds: float = 0.0
    request_count: int = 0
    tool_call_count: int = 0
    actual_model: str = "unknown"
    actual_thinking: str = "unknown"
    termination_reason: str = "unknown"
    session_file: str = ""
    session_files_json: str = "[]"
    observed_models_json: str = "[]"
    configured_matches_actual: bool = False
    fallback_used: bool = False
    catalog_cost_total: float | None = None
    quota_fraction_used: float | None = None
    quota_bucket: str = ""
    cache_hit_ratio: float | None = None
    max_context_tokens: int | None = None
    long_context_requests: int = 0
    subagent_request_count: int = 0
    quality_score: float | None = None
    judge_cost_total: float = 0.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BenchError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BenchError(f"invalid JSON in {path}: {exc}") from exc


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BenchError(f"could not read {path}: {exc}") from exc


def require_int(value: Any, field_name: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise BenchError(f"{field_name} must be an integer >= {minimum}")
    return value


def require_fraction(value: Any, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 < value <= 1.0:
        raise BenchError(f"{field_name} must be a number in (0, 1]")
    return float(value)


def require_string_list(value: Any, field_name: str, *, allowed: Sequence[str] | None = None) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise BenchError(f"{field_name} must be an array of non-empty strings")
    if allowed is not None:
        unknown = sorted(set(value) - set(allowed))
        if unknown:
            raise BenchError(f"{field_name} contains unknown name(s): {', '.join(unknown)}")
    return tuple(value)


def context_tokens(usage: Mapping[str, int]) -> int:
    """Tokens that occupy the request's context window, cached prefix included."""
    return sum(int(usage.get(key) or 0) for key in CONTEXT_KEYS)


def cache_hit_ratio(input_tokens: int, cache_read_tokens: int, cache_write_tokens: int) -> float | None:
    denominator = input_tokens + cache_read_tokens + cache_write_tokens
    if denominator <= 0:
        return None
    return cache_read_tokens / denominator


def load_classes(path: Path = CLASSES_FILE) -> dict[str, TaskClass]:
    raw = load_json(path)
    if not isinstance(raw, dict):
        raise BenchError(f"class list must be an object: {path}")
    classes = raw.get("classes")
    if not isinstance(classes, dict) or not classes:
        raise BenchError(f"classes in {path} must be a non-empty object")
    parsed: dict[str, TaskClass] = {}
    for class_id, body in classes.items():
        if not isinstance(class_id, str) or not class_id:
            raise BenchError(f"class id in {path} must be a non-empty string")
        if not isinstance(body, dict):
            raise BenchError(f"class {class_id} in {path} must be an object")
        title = body.get("title")
        if not isinstance(title, str) or not title:
            raise BenchError(f"title of class {class_id} in {path} must be a non-empty string")
        weight = body.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or not 0.0 < weight <= 1.0:
            raise BenchError(f"weight of class {class_id} in {path} must be a number in (0, 1]")
        grading = body.get("grading")
        if grading not in GRADING_MODES:
            raise BenchError(f"grading of class {class_id} in {path} must be one of {', '.join(GRADING_MODES)}")
        parsed[class_id] = TaskClass(
            class_id=class_id,
            title=title,
            weight=float(weight),
            grading=grading,
            harness_roles=require_string_list(
                body.get("harness_roles"), f"{path}: {class_id}.harness_roles", allowed=MODEL_ROLES
            ),
            agent_overrides=require_string_list(
                body.get("agent_overrides"), f"{path}: {class_id}.agent_overrides", allowed=AGENT_OVERRIDE_KEYS
            ),
        )
    total = sum(item.weight for item in parsed.values())
    if abs(total - 1.0) > 0.001:
        raise BenchError(f"class weights in {path} must sum to 1.0 +/- 0.001, not {total:.4f}")
    return parsed


def resolve_fixture(relative_path: Any, source: Path) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise BenchError(f"fixture in {source} must be a non-empty string")
    resolved = (BENCH_DIR / relative_path).resolve()
    fixtures_root = (BENCH_DIR / "fixtures").resolve()
    if not resolved.is_relative_to(fixtures_root) or not resolved.is_dir():
        raise BenchError(f"fixture in {source} must name a directory below {fixtures_root}")
    return resolved


def parse_rubric(raw: Any, source: Path, fixture: Path) -> RubricDefinition | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BenchError(f"rubric in {source} must be an object")
    output = raw.get("output")
    if not isinstance(output, str) or not output:
        raise BenchError(f"rubric.output in {source} must be a non-empty string")
    output_path = Path(output)
    if output_path.is_absolute() or ".." in output_path.parts:
        raise BenchError(f"rubric.output in {source} must be a relative path inside the fixture copy")
    reference = raw.get("reference")
    if not isinstance(reference, str) or not reference:
        raise BenchError(f"rubric.reference in {source} must be a non-empty string")
    resolved = (BENCH_DIR / reference).resolve()
    if not resolved.is_relative_to(BENCH_DIR):
        raise BenchError(f"rubric.reference in {source} must stay below {BENCH_DIR}")
    if resolved.is_relative_to((BENCH_DIR / "fixtures").resolve()):
        # The reference is the expected answer. A fixture is copied into the
        # agent's workspace, so a reference stored there would be readable by
        # the candidate it grades.
        raise BenchError(f"rubric.reference in {source} must not live below the fixtures directory")
    if not resolved.is_file():
        raise BenchError(f"rubric.reference in {source} does not name an existing file: {reference}")
    criteria = raw.get("criteria")
    if not isinstance(criteria, list) or not criteria or not all(isinstance(item, str) and item for item in criteria):
        raise BenchError(f"rubric.criteria in {source} must be a non-empty array of non-empty strings")
    context = require_string_list(raw.get("context", []), f"{source}: rubric.context")
    for relative in context:
        context_file = (fixture / relative).resolve()
        # An absolute path is rejected even when it lands inside the fixture:
        # the judge prompt labels these files by the relative path the task
        # gave, and the runner copies the fixture elsewhere before the run.
        if (
            Path(relative).is_absolute()
            or not context_file.is_relative_to(fixture)
            or not context_file.is_file()
        ):
            raise BenchError(f"rubric.context in {source} must name a fixture-relative file: {relative}")
    threshold = raw.get("pass_threshold", DEFAULT_PASS_THRESHOLD)
    return RubricDefinition(
        output=output,
        reference=resolved,
        criteria=tuple(criteria),
        pass_threshold=require_fraction(threshold, f"{source}: rubric.pass_threshold"),
        context=context,
    )


def load_tasks(classes: Mapping[str, TaskClass]) -> list[TaskDefinition]:
    task_files = sorted(TASKS_DIR.glob("*.json"))
    if not task_files:
        raise BenchError(f"no task definitions found in {TASKS_DIR}")
    tasks: list[TaskDefinition] = []
    seen: set[str] = set()
    for source in task_files:
        raw = load_json(source)
        if not isinstance(raw, dict):
            raise BenchError(f"task definition must be an object: {source}")
        task_id = raw.get("id")
        title = raw.get("title")
        task_class = raw.get("class")
        prompt = raw.get("prompt")
        verify = raw.get("verify")
        estimated = raw.get("estimated_usage")
        protected = raw.get("protected_paths", [])
        if not isinstance(task_id, str) or not task_id:
            raise BenchError(f"id in {source} must be a non-empty string")
        if task_id in seen:
            raise BenchError(f"duplicate task id: {task_id}")
        if not isinstance(title, str) or not title:
            raise BenchError(f"title in {source} must be a non-empty string")
        if not isinstance(task_class, str) or not task_class:
            raise BenchError(f"class in {source} must be a non-empty string")
        if task_class not in classes:
            raise BenchError(
                f"class {task_class} in {source} is not defined in {CLASSES_FILE}; "
                f"known classes: {', '.join(sorted(classes))}"
            )
        if not isinstance(prompt, str) or not prompt.strip():
            raise BenchError(f"prompt in {source} must be a non-empty string")
        if not isinstance(verify, list) or not verify or not all(isinstance(x, str) and x for x in verify):
            raise BenchError(f"verify in {source} must be a non-empty string array")
        if not isinstance(estimated, dict) or set(estimated) != set(TOKEN_KEYS):
            raise BenchError(f"estimated_usage in {source} must contain exactly {', '.join(TOKEN_KEYS)}")
        usage = {key: require_int(estimated[key], f"{source}: estimated_usage.{key}") for key in TOKEN_KEYS}
        if not isinstance(protected, list) or not all(isinstance(x, str) and x for x in protected):
            raise BenchError(f"protected_paths in {source} must be a string array")
        fixture = resolve_fixture(raw.get("fixture"), source)
        for relative in protected:
            protected_file = (fixture / relative).resolve()
            if not protected_file.is_relative_to(fixture) or not protected_file.is_file():
                raise BenchError(f"protected path does not name a fixture file: {relative} ({source})")
        rubric = parse_rubric(raw.get("rubric"), source, fixture)
        expects_rubric = classes[task_class].grading == "rubric"
        if expects_rubric and rubric is None:
            raise BenchError(f"class {task_class} is graded by rubric, so {source} must define a rubric block")
        if rubric is not None and not expects_rubric:
            raise BenchError(f"class {task_class} is graded by verify alone, so {source} must not define a rubric")
        tasks.append(
            TaskDefinition(
                task_id=task_id,
                title=title,
                task_class=task_class,
                fixture=fixture,
                prompt=prompt.strip(),
                verify=tuple(verify),
                timeout_seconds=require_int(raw.get("timeout_seconds"), f"{source}: timeout_seconds", minimum=1),
                default_repetitions=require_int(
                    raw.get("default_repetitions"), f"{source}: default_repetitions", minimum=1
                ),
                estimated_usage=usage,
                protected_paths=tuple(protected),
                rubric=rubric,
            )
        )
        seen.add(task_id)
    return tasks


def load_config(path: Path) -> dict[str, Any]:
    raw = load_json(path)
    if not isinstance(raw, dict):
        raise BenchError(f"configuration must be an object: {path}")
    candidates = raw.get("candidates")
    if not isinstance(candidates, list) or not candidates or not all(isinstance(x, str) and x for x in candidates):
        raise BenchError(f"candidates in {path} must be a non-empty string array")
    if len(candidates) != len(set(candidates)):
        raise BenchError(f"candidates in {path} must not contain duplicates")
    budget = raw.get("default_budget_usd")
    if not isinstance(budget, (int, float)) or isinstance(budget, bool) or budget <= 0:
        raise BenchError(f"default_budget_usd in {path} must be positive")
    warning = require_int(raw.get("minimum_samples_warning"), f"{path}: minimum_samples_warning", minimum=1)
    judge_selector = raw.get("judge")
    if not isinstance(judge_selector, str) or not judge_selector:
        raise BenchError(f"judge in {path} must be a non-empty model selector")
    split_selector(judge_selector)
    variants = raw.get("variants", {})
    if not isinstance(variants, dict):
        raise BenchError(f"variants in {path} must be an object")
    parsed_variants: dict[str, dict[str, Any]] = {}
    for name, overrides in variants.items():
        if not isinstance(name, str) or not name or VARIANT_SEPARATOR in name:
            raise BenchError(f"variant name in {path} must be a non-empty string without {VARIANT_SEPARATOR!r}")
        if not isinstance(overrides, dict) or not overrides:
            raise BenchError(f"variant {name} in {path} must be a non-empty object of dotted config keys")
        # Checking the overlay now turns a malformed dotted key, or a variant
        # that would move a pinned role, into a load error instead of a failure
        # in the middle of a paid run.
        nest_dotted(overrides)
        for key in overrides:
            collision = pinned_overlay_collision(key)
            if collision:
                raise BenchError(
                    f"variant {name} in {path} sets {key}, which would move {collision}; "
                    "the runner pins that path to the candidate under test"
                )
        parsed_variants[name] = dict(overrides)
    return {
        "candidates": candidates,
        "default_budget_usd": float(budget),
        "minimum_samples_warning": warning,
        "judge": judge_selector,
        "variants": parsed_variants,
    }


def split_candidate(candidate: str) -> tuple[str, str]:
    """Split `<selector>[@<variant>]` into the model selector and the variant name."""
    selector, separator, variant = candidate.partition(VARIANT_SEPARATOR)
    if separator and not variant:
        raise BenchError(f"candidate variant must not be empty: {candidate}")
    if variant and selector.startswith(f"{AGY_PROVIDER}/"):
        raise BenchError(
            f"an {AGY_PROVIDER} candidate takes no {VARIANT_SEPARATOR}variant because that CLI has no "
            f"config overlay: {candidate}"
        )
    if not selector:
        raise BenchError(f"candidate must name a model selector: {candidate}")
    return selector, variant


def split_selector(selector: str) -> tuple[str, str, str]:
    if "/" not in selector:
        raise BenchError(f"model selector must contain a provider and model: {selector}")
    if selector.startswith(f"{AGY_PROVIDER}/"):
        model = selector.split("/", 1)[1]
        if not model or ":" in model:
            raise BenchError(f"an {AGY_PROVIDER} selector is `{AGY_PROVIDER}/<model-id>`: {selector}")
        return AGY_PROVIDER, model, ""
    base, separator, thinking = selector.rpartition(":")
    if not separator or "/" not in base or not thinking:
        raise BenchError(f"model selector must include a thinking suffix: {selector}")
    provider, model = base.split("/", 1)
    if not provider or not model:
        raise BenchError(f"invalid model selector: {selector}")
    return provider, model, thinking


def nest_dotted(overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Turn `{"a.b": 1}` into `{"a": {"b": 1}}`, merging keys that share a prefix."""
    result: dict[str, Any] = {}
    for dotted, value in overrides.items():
        if not isinstance(dotted, str) or not dotted:
            raise BenchError(f"overlay key must be a non-empty dotted config path: {dotted!r}")
        parts = dotted.split(".")
        if not all(parts):
            raise BenchError(f"overlay key must not contain an empty path segment: {dotted!r}")
        cursor = result
        for part in parts[:-1]:
            nested = cursor.setdefault(part, {})
            if not isinstance(nested, dict):
                raise BenchError(f"overlay key {dotted} collides with the scalar already set at {part}")
            cursor = nested
        leaf = parts[-1]
        if isinstance(cursor.get(leaf), dict) and not isinstance(value, dict):
            raise BenchError(f"overlay key {dotted} collides with the object already set at {leaf}")
        cursor[leaf] = value
    return result


def pinned_overlay_collision(key: str) -> str:
    """The pinned path a variant key would move, or `''` when it moves none."""
    for path in PINNED_OVERLAY_PATHS:
        if key == path or key.startswith(f"{path}.") or path.startswith(f"{key}."):
            return path
    return ""


def candidate_overlay(selector: str, overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Build the one-run OMP overlay that pins every role to one candidate.

    `retry.fallbackChains` is emptied and `retry.modelFallback` is switched off:
    an emptied record overlay still merges with the user's own chains, and a
    transport error (observed: "socket connection was closed unexpectedly")
    then substituted another model mid-run under the candidate's name.
    """
    for key in overrides:
        collision = pinned_overlay_collision(key)
        if collision:
            raise BenchError(
                f"variant key {key} would move {collision}, which the runner pins to the candidate"
            )
    dotted: dict[str, Any] = {f"modelRoles.{role}": selector for role in MODEL_ROLES}
    dotted.update({f"task.agentModelOverrides.{key}": selector for key in AGENT_OVERRIDE_KEYS})
    dotted["retry.fallbackChains"] = {}
    dotted["retry.modelFallback"] = False
    dotted["retry.usageAwareFallback"] = False
    dotted.update(overrides)
    return nest_dotted(dotted)


def load_model_rates(path: Path = MODEL_DB) -> dict[tuple[str, str], ModelRate]:
    if not path.is_file():
        raise BenchError(f"OMP model catalog not found: {path}")
    rates: dict[tuple[str, str], ModelRate] = {}
    try:
        with sqlite3.connect(path) as connection:
            rows = connection.execute("SELECT provider_id, models FROM model_cache").fetchall()
    except sqlite3.Error as exc:
        raise BenchError(f"could not read OMP model catalog {path}: {exc}") from exc
    for provider, encoded_models in rows:
        try:
            models = json.loads(encoded_models)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(models, list):
            continue
        for model in models:
            if not isinstance(model, dict) or not isinstance(model.get("id"), str):
                continue
            cost = model.get("cost")
            if not isinstance(cost, dict):
                continue
            if not all(isinstance(cost.get(key), (int, float)) for key in TOKEN_KEYS):
                continue
            rates[(provider, model["id"])] = ModelRate(
                base={key: float(cost[key]) for key in TOKEN_KEYS},
                **long_context_band(cost.get("longContext")),
            )
    return rates


def long_context_band(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"long_context": None, "long_context_threshold": None}
    threshold = raw.get("inputThreshold")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or threshold <= 0:
        return {"long_context": None, "long_context_threshold": None}
    if not all(isinstance(raw.get(key), (int, float)) for key in TOKEN_KEYS):
        return {"long_context": None, "long_context_threshold": None}
    return {
        "long_context": {key: float(raw[key]) for key in TOKEN_KEYS},
        "long_context_threshold": int(threshold),
    }


def cost_for_usage(usage: Mapping[str, int], rate: Mapping[str, float]) -> float:
    return sum(int(usage.get(key) or 0) * rate[key] for key in TOKEN_KEYS) / 1_000_000


def candidate_estimate(task: TaskDefinition, candidate: str, rates: Mapping[tuple[str, str], ModelRate]) -> float:
    provider, model, _ = split_selector(split_candidate(candidate)[0])
    if provider == AGY_PROVIDER:
        return 0.0
    rate = rates.get((provider, model))
    if rate is None:
        raise BenchError(f"no catalog pricing for candidate {provider}/{model}")
    return rate.cost(task.estimated_usage)


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def protected_digests(task: TaskDefinition, fixture: Path | None = None) -> dict[str, str]:
    base = fixture or task.fixture
    return {relative: digest_file(base / relative) for relative in task.protected_paths}


def fixture_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = item.relative_to(path).as_posix()
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        with item.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(block)
        hasher.update(b"\0")
    return hasher.hexdigest()


def run_verify(task: TaskDefinition, cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        return subprocess.run(
            task.verify,
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            timeout=min(task.timeout_seconds, 120),
            check=False,
        )
    except FileNotFoundError as exc:
        raise BenchError(f"verification executable not found for {task.task_id}: {task.verify[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise BenchError(f"verification timed out for {task.task_id}") from exc


def abbreviated_output(completed: subprocess.CompletedProcess[str], limit: int = 1200) -> str:
    output = "\n".join(piece.strip() for piece in (completed.stdout, completed.stderr) if piece.strip())
    if len(output) > limit:
        return output[:limit] + "..."
    return output


def judge_prompt(
    prompt: str,
    criteria: Sequence[str],
    reference_text: str,
    candidate_text: str,
    context: Sequence[tuple[str, str]] = (),
) -> str:
    numbered = "\n".join(f"{index}. {criterion}" for index, criterion in enumerate(criteria, start=1))
    # The judge runs in an empty directory and cannot open the fixture, so the
    # inputs a criterion measures fidelity against have to travel in the prompt.
    inputs = "".join(f"\n## 입력 자료: {relative}\n{text}\n" for relative, text in context)
    return (
        "You are grading one candidate deliverable against a reference deliverable.\n"
        "Score every criterion as an integer: 0 (not met), 1 (partially met), 2 (fully met).\n"
        f"Return exactly {len(criteria)} scores, in the order the criteria are listed.\n"
        'Output one JSON object and nothing else: {"scores": [<integers>], "rationale": "<one paragraph>"}.\n'
        "No prose before or after it, no code fence, no markdown.\n"
        "Grade only what the deliverables say. Do not run tools and do not ask anything.\n"
        f"\n=== TASK GIVEN TO THE CANDIDATE ===\n{prompt}\n"
        f"\n=== CRITERIA ===\n{numbered}\n"
        f"{inputs}"
        f"\n=== REFERENCE DELIVERABLE ===\n{reference_text}\n"
        f"\n=== CANDIDATE DELIVERABLE ===\n{candidate_text}\n"
    )


def judge_stream_payload(stdout: str) -> tuple[str, float]:
    """Assistant text and recorded cost of the last `message_end` of a `--mode json` stream.

    Every line of that output is one event. Only `message_end` carries the
    finished message, so the deltas before it are ignored, and the last one wins
    because a judge turn that somehow produced two messages is scored on the
    final answer.
    """
    text = ""
    cost = 0.0
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        text = (
            "".join(
                part["text"]
                for part in content
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
            )
            if isinstance(content, list)
            else ""
        )
        usage = message.get("usage")
        total = usage.get("cost", {}).get("total") if isinstance(usage, dict) else None
        cost = float(total) if isinstance(total, (int, float)) and not isinstance(total, bool) else 0.0
    return text, cost


def parse_judge_verdict(text: str, criteria_count: int) -> tuple[tuple[int, ...], str] | None:
    """Read `{"scores": [...], "rationale": "..."}`; `None` means the verdict is unusable.

    The whole reply has to be that object. Digging a JSON object out of prose
    would score a reply that ignored the output contract, and a judge that
    ignores its output contract is not a measurement.
    """
    try:
        payload = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    scores = payload.get("scores")
    if not isinstance(scores, list) or len(scores) != criteria_count:
        return None
    parsed: list[int] = []
    for score in scores:
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 2:
            return None
        parsed.append(score)
    rationale = payload.get("rationale")
    return tuple(parsed), rationale if isinstance(rationale, str) else ""


def rubric_quality_score(scores: Sequence[int], criteria_count: int) -> float:
    if criteria_count <= 0:
        raise BenchError("a rubric needs at least one criterion")
    return sum(scores) / (2 * criteria_count)


def rubric_verdict_passed(verdict: JudgeResult, pass_threshold: float) -> bool:
    """Whether a judged run clears its rubric threshold.

    An unusable verdict never passes: a run whose quality could not be read is
    not a run that met the bar.
    """
    if verdict.parse_error or verdict.quality_score is None:
        return False
    return verdict.quality_score >= pass_threshold


def judge(
    prompt: str,
    criteria: Sequence[str],
    reference_text: str,
    candidate_text: str,
    judge_selector: str,
    context: Sequence[tuple[str, str]] = (),
) -> JudgeResult:
    """Score one deliverable with the rubric judge; never retried, never fatal.

    The judge runs in an empty temporary directory so it cannot read the task
    fixture, the repository, or the candidate's workspace, and with
    `--no-session` because the cost it reports comes from the event stream.
    """
    if not criteria:
        raise BenchError("a rubric needs at least one criterion")
    split_selector(judge_selector)
    work_dir = Path(tempfile.mkdtemp(prefix="bench-judge-"))
    command = [
        "omp",
        "-p",
        judge_prompt(prompt, criteria, reference_text, candidate_text, context),
        "--model",
        judge_selector,
        "--mode",
        "json",
        "--no-skills",
        "--no-session",
        "--append-system-prompt",
        BENCH_APPEND_SYSTEM_PROMPT,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=work_dir,
            text=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=JUDGE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BenchError("omp executable was not found") from exc
    except subprocess.TimeoutExpired:
        return JudgeResult(None, rationale="the judge call exceeded its timeout", parse_error=True)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    text, cost = judge_stream_payload(completed.stdout)
    verdict = parse_judge_verdict(text, len(criteria))
    if verdict is None:
        return JudgeResult(
            None,
            rationale=text.strip() or abbreviated_output(completed) or "the judge produced no message",
            cost_total=cost,
            parse_error=True,
        )
    scores, rationale = verdict
    return JudgeResult(
        rubric_quality_score(scores, len(criteria)),
        scores=scores,
        rationale=rationale,
        cost_total=cost,
    )


def grade_rubric(task: TaskDefinition, work_copy: Path, judge_selector: str) -> JudgeResult:
    rubric = task.rubric
    if rubric is None:
        raise BenchError(f"task {task.task_id} has no rubric to grade")
    produced = (work_copy / rubric.output).resolve()
    if not produced.is_relative_to(work_copy.resolve()) or not produced.is_file():
        return JudgeResult(0.0, rationale=f"the candidate wrote no {rubric.output}", invoked=False)
    # The context files are read from the original fixture, never from the work
    # copy: the candidate may have edited its copy, and the judge has to see
    # the input the task actually gave it.
    context = [(relative, read_text_file(task.fixture / relative)) for relative in rubric.context]
    return judge(
        task.prompt,
        rubric.criteria,
        read_text_file(rubric.reference),
        read_text_file(produced),
        judge_selector,
        context,
    )


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise BenchError(f"invalid session JSONL at {path}:{line_number}: {exc}") from exc
                if isinstance(value, dict):
                    entries.append(value)
    except OSError as exc:
        raise BenchError(f"could not read session file {path}: {exc}") from exc
    return entries


def ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def timed_out_process(
    command: Sequence[str], exc: subprocess.TimeoutExpired
) -> subprocess.CompletedProcess[str]:
    def text(value: bytes | str | None) -> str:
        if value is None:
            return ""
        return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value

    return subprocess.CompletedProcess(
        list(command), EXTERNAL_TIMEOUT_EXIT, text(exc.stdout), text(exc.stderr)
    )



def session_metrics(
    session_dir: Path,
    configured_selector: str,
    rates: Mapping[tuple[str, str], ModelRate],
    omp_return_code: int,
) -> SessionMetrics:
    files = sorted(session_dir.rglob("*.jsonl"))
    metrics = SessionMetrics()
    all_models: list[str] = []
    main_models: list[str] = []
    all_thinking: list[str] = []
    main_thinking: list[str] = []
    exit_reasons: list[str] = []
    fallback_used = False
    catalog_total = 0.0
    catalog_complete = True
    main_files: list[Path] = []
    max_context = 0

    for session_file in files:
        entries = parse_jsonl(session_file)
        init_entries = [entry for entry in entries if entry.get("type") == "session_init"]
        is_subagent = any(entry.get("agent") for entry in init_entries)
        if not is_subagent:
            main_files.append(session_file)
        for entry in entries:
            entry_type = entry.get("type")
            if entry_type == "model_change":
                changed_model = entry.get("model")
                if isinstance(changed_model, str):
                    all_models.append(changed_model)
                    if not is_subagent:
                        main_models.append(changed_model)
                fallback_used = fallback_used or bool(entry.get("resolvedModelIsFallback"))
            elif entry_type == "thinking_level_change":
                level = entry.get("thinkingLevel")
                if isinstance(level, str):
                    all_thinking.append(level)
                    if not is_subagent:
                        main_thinking.append(level)
            elif entry_type == "custom":
                if entry.get("customType") == "tool_execution_start":
                    metrics.tool_call_count += 1
                elif entry.get("customType") == "session_exit":
                    data = entry.get("data")
                    if isinstance(data, dict) and isinstance(data.get("reason"), str):
                        exit_reasons.append(data["reason"])
            elif entry_type == "message":
                message = entry.get("message")
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                metrics.request_count += 1
                if is_subagent:
                    metrics.subagent_request_count += 1
                request_usage = {key: int(usage.get(key) or 0) for key in TOKEN_KEYS}
                metrics.input_tokens += request_usage["input"]
                metrics.output_tokens += request_usage["output"]
                metrics.cache_read_tokens += request_usage["cacheRead"]
                metrics.cache_write_tokens += request_usage["cacheWrite"]
                request_context = context_tokens(request_usage)
                max_context = max(max_context, request_context)
                cost = usage.get("cost")
                if isinstance(cost, dict) and isinstance(cost.get("total"), (int, float)):
                    metrics.cost_total += float(cost["total"])
                provider = message.get("provider")
                model = message.get("model")
                if isinstance(provider, str) and isinstance(model, str):
                    full_model = f"{provider}/{model}"
                    all_models.append(full_model)
                    if not is_subagent:
                        main_models.append(full_model)
                    rate = rates.get((provider, model))
                    if rate is None:
                        catalog_complete = False
                    else:
                        catalog_total += rate.cost(request_usage)
                        if rate.is_long_context(request_context):
                            metrics.long_context_requests += 1
                else:
                    catalog_complete = False

    unique_models = ordered_unique(all_models)
    unique_main_models = ordered_unique(main_models) or unique_models
    unique_main_thinking = ordered_unique(main_thinking) or ordered_unique(all_thinking)
    metrics.actual_model = ",".join(unique_main_models) if unique_main_models else "unknown"
    metrics.actual_thinking = ",".join(unique_main_thinking) if unique_main_thinking else "unknown"
    metrics.fallback_used = fallback_used
    configured_provider, configured_model, configured_thinking = split_selector(configured_selector)
    configured_base = f"{configured_provider}/{configured_model}"
    metrics.configured_matches_actual = (
        unique_main_models == [configured_base]
        and unique_main_thinking == [configured_thinking]
        and not fallback_used
    )
    reasons = ordered_unique(exit_reasons)
    if reasons:
        metrics.termination_reason = ",".join(reasons)
    elif omp_return_code == 0:
        metrics.termination_reason = "process_exit_0"
    else:
        metrics.termination_reason = f"process_exit_{omp_return_code}"
    selected_files = main_files or files
    metrics.session_file = str(selected_files[0]) if selected_files else ""
    metrics.session_files_json = json.dumps([str(path) for path in files], ensure_ascii=False)
    metrics.observed_models_json = json.dumps(unique_models, ensure_ascii=False)
    metrics.catalog_cost_total = catalog_total if catalog_complete else None
    metrics.cache_hit_ratio = cache_hit_ratio(
        metrics.input_tokens, metrics.cache_read_tokens, metrics.cache_write_tokens
    )
    metrics.max_context_tokens = max_context if metrics.request_count else None
    return metrics


def agy_quota_snapshot() -> dict[str, float]:
    """Remaining fraction per quota bucket, read through the free `/usage` command."""
    try:
        completed = subprocess.run(
            [AGY_PROVIDER, "-p", "/usage", "--output-format", "json"],
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BenchError(f"{AGY_PROVIDER} executable was not found") from exc
    except subprocess.TimeoutExpired:
        return {}
    if completed.returncode != 0:
        return {}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}
    data = payload.get("command", {}).get("data", {})
    remaining: dict[str, float] = {}
    for group in data.get("groups", []) if isinstance(data, dict) else []:
        for bucket in group.get("buckets", []) if isinstance(group, dict) else []:
            bucket_id = bucket.get("id")
            fraction = bucket.get("remaining_fraction")
            if isinstance(bucket_id, str) and isinstance(fraction, (int, float)):
                remaining[bucket_id] = float(fraction)
    return remaining


def agy_quota_bucket(model: str) -> str:
    key = "gemini" if model.startswith(AGY_GEMINI_PREFIX) else "third-party"
    return AGY_QUOTA_BUCKETS[key]


def agy_metrics(stdout: str, selector: str, exit_code: int) -> SessionMetrics:
    """Fold the `--output-format stream-json` event stream into one run's metrics.

    Only the final `result` event carries whole-run token totals; the per-step
    events are what make request and tool counts observable at all, because the
    plain `json` output reports neither. Per-request context is therefore not
    observable for this provider, so `max_context_tokens` stays unset.
    """
    metrics = SessionMetrics()
    observed_models: list[str] = []
    conversation_id = ""
    status = ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("event")
        if kind == "init":
            conversation_id = event.get("conversation_id") or conversation_id
            init = event.get("init")
            if isinstance(init, dict) and isinstance(init.get("model"), str):
                observed_models.append(f"{AGY_PROVIDER}/{init['model']}")
        elif kind == "step_update":
            step = event.get("step_update")
            if not isinstance(step, dict) or step.get("state") != "DONE":
                continue
            if step.get("step_type") == "agent_response":
                metrics.request_count += 1
            elif step.get("step_type") == "tool":
                metrics.tool_call_count += 1
        elif kind == "result":
            result = event.get("result")
            if not isinstance(result, dict):
                continue
            conversation_id = result.get("conversation_id") or conversation_id
            status = result.get("status") or status
            usage = result.get("usage")
            if isinstance(usage, dict):
                metrics.input_tokens = int(usage.get("input_tokens") or 0)
                metrics.output_tokens = int(usage.get("output_tokens") or 0)
                metrics.cache_read_tokens = int(usage.get("cache_read_tokens") or 0)

    _, model, _ = split_selector(selector)
    # The CLI never echoes which model actually served the turn beyond the id it
    # was asked for, so the routing check is vacuous for this provider and the
    # report says so rather than claiming a verified match.
    metrics.actual_model = ordered_unique(observed_models)[0] if observed_models else selector
    metrics.actual_thinking = "n/a"
    metrics.observed_models_json = json.dumps(ordered_unique(observed_models), ensure_ascii=False)
    metrics.configured_matches_actual = metrics.actual_model == f"{AGY_PROVIDER}/{model}"
    metrics.fallback_used = False
    metrics.cost_total = 0.0
    metrics.catalog_cost_total = None
    metrics.quota_bucket = agy_quota_bucket(model)
    metrics.cache_hit_ratio = cache_hit_ratio(
        metrics.input_tokens, metrics.cache_read_tokens, metrics.cache_write_tokens
    )
    if status:
        metrics.termination_reason = status
    elif exit_code == 0:
        metrics.termination_reason = "process_exit_0"
    else:
        metrics.termination_reason = f"process_exit_{exit_code}"
    metrics.session_file = (
        str(AGY_CONVERSATIONS / f"{conversation_id}.db") if conversation_id else ""
    )
    metrics.session_files_json = json.dumps(
        [metrics.session_file] if metrics.session_file else [], ensure_ascii=False
    )
    return metrics


def migrate_schema(connection: sqlite3.Connection) -> None:
    """Bring a database written by an earlier runner up to date.

    The exit-code column was named after OMP when that was the only runner, and
    the quota columns did not exist because no candidate spent quota instead of
    money. Renaming rather than adding a parallel column keeps one meaning per
    column for the rows already recorded. The class, variant, rubric, judge and
    context columns arrived with task classes; rows written before them keep
    NULL where the value was never measured, and `''` where the concept did not
    exist.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
    if not columns:
        return
    if "omp_exit_code" in columns and "agent_exit_code" not in columns:
        connection.execute("ALTER TABLE runs RENAME COLUMN omp_exit_code TO agent_exit_code")
    additions = (
        ("quota_bucket", "TEXT NOT NULL DEFAULT ''"),
        ("quota_fraction_used", "REAL"),
        ("variant", "TEXT NOT NULL DEFAULT ''"),
        ("task_class", "TEXT NOT NULL DEFAULT ''"),
        ("quality_score", "REAL"),
        ("judge_cost_total", "REAL NOT NULL DEFAULT 0"),
        ("cache_hit_ratio", "REAL"),
        ("max_context_tokens", "INTEGER"),
        ("long_context_requests", "INTEGER"),
        ("subagent_request_count", "INTEGER"),
        ("judge", "TEXT NOT NULL DEFAULT ''"),
    )
    for name, declaration in additions:
        if name not in columns:
            connection.execute(f"ALTER TABLE runs ADD COLUMN {name} {declaration}")


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_title TEXT NOT NULL,
                    task_class TEXT NOT NULL DEFAULT '',
                    candidate TEXT NOT NULL,
                    variant TEXT NOT NULL DEFAULT '',
                    repeat_index INTEGER NOT NULL,
                    passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
                    protected_files_unchanged INTEGER NOT NULL CHECK (protected_files_unchanged IN (0, 1)),
                    quality_score REAL,
                    judge TEXT NOT NULL DEFAULT '',
                    duration_seconds REAL NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cache_read_tokens INTEGER NOT NULL,
                    cache_write_tokens INTEGER NOT NULL,
                    cache_hit_ratio REAL,
                    max_context_tokens INTEGER,
                    long_context_requests INTEGER,
                    cost_total REAL NOT NULL,
                    catalog_cost_total REAL,
                    judge_cost_total REAL NOT NULL DEFAULT 0,
                    request_count INTEGER NOT NULL,
                    subagent_request_count INTEGER,
                    tool_call_count INTEGER NOT NULL,
                    actual_model TEXT NOT NULL,
                    actual_thinking TEXT NOT NULL,
                    configured_matches_actual INTEGER NOT NULL CHECK (configured_matches_actual IN (0, 1)),
                    fallback_used INTEGER NOT NULL CHECK (fallback_used IN (0, 1)),
                    observed_models_json TEXT NOT NULL,
                    termination_reason TEXT NOT NULL,
                    agent_exit_code INTEGER NOT NULL,
                    verify_exit_code INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    session_file TEXT NOT NULL,
                    session_files_json TEXT NOT NULL,
                    quota_bucket TEXT NOT NULL DEFAULT '',
                    quota_fraction_used REAL
                )
                """
            )
            # An existing database predates the newer columns, so migrate
            # before the indexes: `runs_class_idx` names `task_class`, which
            # `CREATE TABLE IF NOT EXISTS` did not add to that file.
            migrate_schema(connection)
            connection.execute("CREATE INDEX IF NOT EXISTS runs_candidate_idx ON runs(candidate)")
            connection.execute("CREATE INDEX IF NOT EXISTS runs_task_idx ON runs(task_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS runs_class_idx ON runs(task_class)")
    except sqlite3.Error as exc:
        raise BenchError(f"could not initialize result database {path}: {exc}") from exc


def insert_run(path: Path, row: dict[str, Any]) -> int:
    columns = tuple(row)
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO runs ({', '.join(columns)}) VALUES ({placeholders})"
    try:
        with sqlite3.connect(path) as connection:
            cursor = connection.execute(sql, tuple(row[column] for column in columns))
            return int(cursor.lastrowid)
    except sqlite3.Error as exc:
        raise BenchError(f"could not write result database {path}: {exc}") from exc


def select_tasks(tasks: Sequence[TaskDefinition], selected: Sequence[str] | None) -> list[TaskDefinition]:
    if not selected:
        return list(tasks)
    by_id = {task.task_id: task for task in tasks}
    unknown = sorted(set(selected) - set(by_id))
    if unknown:
        raise BenchError(f"unknown task id(s): {', '.join(unknown)}")
    selected_set = set(selected)
    return [task for task in tasks if task.task_id in selected_set]


def select_models(config: Mapping[str, Any], selected: Sequence[str] | None) -> list[str]:
    models = list(selected) if selected else list(config["candidates"])
    if len(models) != len(set(models)):
        raise BenchError("model selectors must not contain duplicates")
    for candidate in models:
        selector, variant = split_candidate(candidate)
        split_selector(selector)
        if variant and variant not in config["variants"]:
            known = ", ".join(sorted(config["variants"])) or "none"
            raise BenchError(f"unknown variant {variant} in candidate {candidate}; configured variants: {known}")
    return models


def validate_task_baseline(task: TaskDefinition) -> None:
    fixture_before = fixture_digest(task.fixture)
    work_parent = Path(tempfile.mkdtemp(prefix=f"omp-bench-preflight-{task.task_id}-"))
    work_copy = work_parent / "workspace"
    try:
        shutil.copytree(task.fixture, work_copy)
        baseline = run_verify(task, work_copy)
        if baseline.returncode == 0:
            raise BenchError(f"task {task.task_id} is invalid: verification already passes before the task")
    finally:
        shutil.rmtree(work_parent, ignore_errors=True)
    if fixture_digest(task.fixture) != fixture_before:
        raise BenchError(f"original fixture changed during preflight: {task.fixture}")


def run_omp(
    task: TaskDefinition,
    candidate: str,
    work_copy: Path,
    session_dir: Path,
    rates: Mapping[tuple[str, str], ModelRate],
    variant_overrides: Mapping[str, Any],
) -> tuple[subprocess.CompletedProcess[str], SessionMetrics]:
    selector = split_candidate(candidate)[0]
    overlay_path: Path | None = None
    try:
        overlay = candidate_overlay(selector, variant_overrides)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", prefix="omp-bench-overlay-", delete=False
        ) as handle:
            json.dump(overlay, handle, ensure_ascii=False)
            handle.write("\n")
            overlay_path = Path(handle.name)
        command = [
            "omp",
            "-p",
            task.prompt,
            "--config",
            str(overlay_path),
            "--model",
            selector,
            "--cwd",
            str(work_copy),
            "--auto-approve",
            "--session-dir",
            str(session_dir),
            "--max-time",
            str(task.timeout_seconds),
            "--append-system-prompt",
            BENCH_APPEND_SYSTEM_PROMPT,
        ]
        try:
            completed = subprocess.run(
                command,
                text=True,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=task.timeout_seconds + 45,
                check=False,
            )
        except FileNotFoundError as exc:
            raise BenchError("omp executable was not found") from exc
        except subprocess.TimeoutExpired as exc:
            completed = timed_out_process(command, exc)
            print(
                f"  omp exceeded the external timeout for {task.task_id} on {candidate}; recorded as failed",
                file=sys.stderr,
            )
        metrics = session_metrics(session_dir, selector, rates, completed.returncode)
        if completed.returncode == EXTERNAL_TIMEOUT_EXIT:
            metrics.termination_reason = f"{EXTERNAL_TIMEOUT},{metrics.termination_reason}"
        return completed, metrics
    finally:
        if overlay_path is not None:
            overlay_path.unlink(missing_ok=True)


def run_agy(
    task: TaskDefinition,
    candidate: str,
    work_copy: Path,
) -> tuple[subprocess.CompletedProcess[str], SessionMetrics]:
    """Run one Antigravity CLI candidate inside the fixture copy.

    The harness customizations stay on. Their always-on rule already forbids a
    `herdr-hitl` call in an unattended run, which is what the OMP backend has to
    buy with `--append-system-prompt`, and this CLI has no equivalent flag.

    `--add-dir` is mandatory, not a convenience. In print mode the CLI ignores
    the process working directory and opens the default project rooted at
    `~/.gemini/antigravity-cli/scratch`, so without it the agent sees an empty
    workspace, goes looking for the task elsewhere on the filesystem, and can
    reach the original fixture instead of this copy.
    """
    selector, _ = split_candidate(candidate)
    _, model, _ = split_selector(selector)
    bucket = agy_quota_bucket(model)
    before = agy_quota_snapshot()
    command = [
        AGY_PROVIDER,
        "-p",
        task.prompt,
        "--model",
        model,
        "--output-format",
        "stream-json",
        "--dangerously-skip-permissions",
        "--add-dir",
        str(work_copy),
        "--print-timeout",
        f"{task.timeout_seconds}s",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=work_copy,
            text=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=task.timeout_seconds + 45,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BenchError(f"{AGY_PROVIDER} executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        completed = timed_out_process(command, exc)
        print(
            f"  {AGY_PROVIDER} exceeded the external timeout for {task.task_id} on {candidate}; recorded as failed",
            file=sys.stderr,
        )
    metrics = agy_metrics(completed.stdout, selector, completed.returncode)
    if completed.returncode == EXTERNAL_TIMEOUT_EXIT:
        metrics.termination_reason = f"{EXTERNAL_TIMEOUT},{metrics.termination_reason}"
    after = agy_quota_snapshot()
    if bucket in before and bucket in after:
        metrics.quota_fraction_used = max(0.0, before[bucket] - after[bucket])
    return completed, metrics


def execute_one(
    task: TaskDefinition,
    candidate: str,
    repeat_index: int,
    batch_id: str,
    db_path: Path,
    rates: Mapping[tuple[str, str], ModelRate],
    variants: Mapping[str, Mapping[str, Any]],
    judge_selector: str,
) -> tuple[int, SessionMetrics, bool]:
    selector, variant = split_candidate(candidate)
    provider, _, _ = split_selector(selector)
    fixture_before = fixture_digest(task.fixture)
    work_parent = Path(tempfile.mkdtemp(prefix=f"bench-{task.task_id}-"))
    work_copy = work_parent / "workspace"
    # Only OMP writes session JSONL; an Antigravity run keeps its transcript in
    # its own conversation store, so it gets no dedicated session directory.
    session_dir = (
        Path(tempfile.mkdtemp(prefix=f"bench-session-{task.task_id}-"))
        if provider != AGY_PROVIDER
        else work_parent / "unused-session"
    )
    try:
        shutil.copytree(task.fixture, work_copy)
        baseline = run_verify(task, work_copy)
        if baseline.returncode == 0:
            raise BenchError(f"task {task.task_id} is invalid: verification already passes before the task")
        protected_before = protected_digests(task, work_copy)
        started = time.monotonic()
        if provider == AGY_PROVIDER:
            completed, metrics = run_agy(task, candidate, work_copy)
        else:
            completed, metrics = run_omp(
                task, candidate, work_copy, session_dir, rates, variants.get(variant, {})
            )
        duration = time.monotonic() - started
        verification = run_verify(task, work_copy)
        protected_after = protected_digests(task, work_copy)
        protected_unchanged = protected_before == protected_after
        passed = verification.returncode == 0 and protected_unchanged
        # The judge only ranks quality above the deterministic gate. A run that
        # already failed `verify` or touched a protected file has nothing to
        # rank, and paying a judge to confirm a decided failure would add cost
        # and a second failure reason to the same row.
        judge_used = ""
        if task.rubric is not None and passed:
            verdict = grade_rubric(task, work_copy, judge_selector)
            metrics.quality_score = verdict.quality_score
            metrics.judge_cost_total = verdict.cost_total
            if verdict.invoked:
                judge_used = judge_selector
            passed = rubric_verdict_passed(verdict, task.rubric.pass_threshold)
            if verdict.parse_error:
                metrics.termination_reason = f"{metrics.termination_reason},{JUDGE_PARSE_ERROR}"
                print(f"  judge verdict unusable: {verdict.rationale}", file=sys.stderr)
        metrics.duration_seconds = duration
        row = {
            "batch_id": batch_id,
            "task_id": task.task_id,
            "task_title": task.title,
            "task_class": task.task_class,
            "candidate": candidate,
            "variant": variant,
            "repeat_index": repeat_index,
            "passed": int(passed),
            "protected_files_unchanged": int(protected_unchanged),
            "quality_score": metrics.quality_score,
            "judge": judge_used,
            "duration_seconds": duration,
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "cache_read_tokens": metrics.cache_read_tokens,
            "cache_write_tokens": metrics.cache_write_tokens,
            "cache_hit_ratio": metrics.cache_hit_ratio,
            "max_context_tokens": metrics.max_context_tokens,
            "long_context_requests": metrics.long_context_requests,
            "cost_total": metrics.cost_total,
            "catalog_cost_total": metrics.catalog_cost_total,
            "judge_cost_total": metrics.judge_cost_total,
            "request_count": metrics.request_count,
            "subagent_request_count": metrics.subagent_request_count,
            "tool_call_count": metrics.tool_call_count,
            "actual_model": metrics.actual_model,
            "actual_thinking": metrics.actual_thinking,
            "configured_matches_actual": int(metrics.configured_matches_actual),
            "fallback_used": int(metrics.fallback_used),
            "observed_models_json": metrics.observed_models_json,
            "termination_reason": metrics.termination_reason,
            "agent_exit_code": completed.returncode,
            "verify_exit_code": verification.returncode,
            "created_at": utc_now(),
            "session_file": metrics.session_file,
            "session_files_json": metrics.session_files_json,
            "quota_bucket": metrics.quota_bucket,
            "quota_fraction_used": metrics.quota_fraction_used,
        }
        run_id = insert_run(db_path, row)
        if not passed:
            reason = "protected verifier files changed" if not protected_unchanged else abbreviated_output(verification)
            if reason:
                print(f"  verification failure: {reason}", file=sys.stderr)
        if completed.returncode != 0:
            details = abbreviated_output(completed)
            print(
                f"  {provider if provider == AGY_PROVIDER else 'omp'} exited with {completed.returncode}: "
                f"{details or 'no process output'}",
                file=sys.stderr,
            )
        return run_id, metrics, passed
    finally:
        shutil.rmtree(work_parent, ignore_errors=True)
        if fixture_digest(task.fixture) != fixture_before:
            raise BenchError(f"original fixture changed during run: {task.fixture}")


def command_run(args: argparse.Namespace) -> int:
    if not FACTS_FILE.is_file():
        raise BenchError(f"repository root check failed; missing {FACTS_FILE}")
    config = load_config(args.config.resolve())
    classes = load_classes()
    tasks = select_tasks(load_tasks(classes), args.task)
    models = select_models(config, args.model)
    rates = load_model_rates()
    judge_selector = args.judge or config["judge"]
    split_selector(judge_selector)
    budget = config["default_budget_usd"] if args.budget_usd is None else args.budget_usd
    if budget <= 0:
        raise BenchError("--budget-usd must be positive")
    combinations: list[tuple[TaskDefinition, str, int, float]] = []
    for task in tasks:
        repetitions = args.repeat if args.repeat is not None else task.default_repetitions
        if repetitions < 1:
            raise BenchError("--repeat must be at least 1")
        for candidate in models:
            estimate = candidate_estimate(task, candidate, rates)
            for repeat_index in range(1, repetitions + 1):
                combinations.append((task, candidate, repeat_index, estimate))

    estimated_total = sum(item[3] for item in combinations)
    judged = [task for task in tasks if task.rubric is not None]
    if args.dry_run:
        print("Dry run: no model calls will be made.")
        print_table(
            ("Task", "Class", "Candidate", "Repeat", "Estimated USD"),
            [
                (task.task_id, task.task_class, candidate, str(repeat_index), format_money(estimate))
                for task, candidate, repeat_index, estimate in combinations
            ],
        )
        print(f"Combinations: {len(combinations)}")
        print(f"Estimated total: {format_money(estimated_total)}")
        print(f"Budget ceiling: {format_money(budget)}")
        if judged:
            print(
                f"Rubric judge: {judge_selector} would grade {len(judged)} judged task(s) "
                f"({', '.join(task.task_id for task in judged)}); judge cost is recorded separately "
                "and is not part of the estimate above."
            )
        if estimated_total > budget:
            print("Budget note: a real run would stop before a combination whose estimate exceeds the remaining budget.")
        return 0

    for task in tasks:
        validate_task_baseline(task)
    initialize_database(args.db.resolve())
    batch_id = str(uuid.uuid4())
    spent = 0.0
    judge_spent = 0.0
    completed_count = 0
    for task, candidate, repeat_index, estimate in combinations:
        remaining = budget - spent
        if estimate > remaining + 1e-12:
            print(
                "Budget stop: next estimated run "
                f"({format_money(estimate)}) exceeds remaining budget ({format_money(max(remaining, 0.0))})."
            )
            break
        print(f"Running {task.task_id} | {candidate} | repetition {repeat_index}")
        run_id, metrics, passed = execute_one(
            task,
            candidate,
            repeat_index,
            batch_id,
            args.db.resolve(),
            rates,
            config["variants"],
            judge_selector,
        )
        completed_count += 1
        spent += metrics.cost_total
        judge_spent += metrics.judge_cost_total
        match = "match" if metrics.configured_matches_actual else "MISMATCH"
        quota = (
            f" quota={metrics.quota_fraction_used * 100:.3f}%"
            if metrics.quota_fraction_used is not None
            else ""
        )
        quality = "" if metrics.quality_score is None else f" quality={metrics.quality_score:.2f}"
        print(
            f"  run={run_id} result={'PASS' if passed else 'FAIL'} actual={metrics.actual_model}:{metrics.actual_thinking} "
            f"routing={match} requests={metrics.request_count} tools={metrics.tool_call_count} "
            f"cost={format_money(metrics.cost_total)}{quota}{quality} elapsed={metrics_duration(metrics)}"
        )
        if spent >= budget:
            print(
                f"Budget stop: cumulative actual cost {format_money(spent)} reached or exceeded "
                f"the {format_money(budget)} ceiling."
            )
            break
    print(
        f"Batch {batch_id}: completed {completed_count}/{len(combinations)} runs; "
        f"actual recorded cost {format_money(spent)}."
    )
    if judge_spent > 0:
        print(f"Judge cost for this batch: {format_money(judge_spent)} (recorded separately from candidate cost).")
    return 0


def metrics_duration(metrics: SessionMetrics) -> str:
    return f"{metrics.duration_seconds:.1f}s"


def fetch_rows(path: Path) -> list[sqlite3.Row]:
    if not path.is_file():
        raise BenchError(f"result database not found: {path}")
    try:
        with sqlite3.connect(path) as connection:
            # Reporting migrates too: a database recorded by an earlier runner
            # must be readable with the current column set instead of failing
            # on a missing column.
            migrate_schema(connection)
            connection.row_factory = sqlite3.Row
            return connection.execute("SELECT * FROM runs ORDER BY id").fetchall()
    except sqlite3.Error as exc:
        raise BenchError(f"could not read result database {path}: {exc}") from exc


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def group_rows(rows: Sequence[sqlite3.Row], keys: Sequence[str]) -> dict[tuple[Any, ...], list[sqlite3.Row]]:
    groups: dict[tuple[Any, ...], list[sqlite3.Row]] = {}
    for row in rows:
        key = tuple(row[column] for column in keys)
        groups.setdefault(key, []).append(row)
    return groups


def format_money(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.6f}"


def format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def format_optional_rate(value: float | None) -> str:
    return "n/a" if value is None else format_rate(value)


def format_quality(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def print_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    all_rows = [tuple(str(cell) for cell in headers)] + [tuple(str(cell) for cell in row) for row in rows]
    widths = [max(len(row[index]) for row in all_rows) for index in range(len(headers))]
    print(" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(all_rows[0])))
    print("-+-".join("-" * width for width in widths))
    for row in all_rows[1:]:
        print(" | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))


def quota_per_task(members: Sequence[sqlite3.Row]) -> float | None:
    """Mean Antigravity quota drawn per task, as a fraction of the weekly bucket.

    Rows written before the Antigravity backend carry NULL here, and so does any
    OMP row, because OMP spends money instead of plan quota.
    """
    values = [row["quota_fraction_used"] for row in members if row["quota_fraction_used"] is not None]
    if not values:
        return None
    return sum(float(value) for value in values) / len(values)


def pass_power_k(members: Sequence[sqlite3.Row]) -> float | None:
    """Share of repeated tasks whose every attempt passed.

    Only tasks with at least two attempts count, because pass^k asks whether a
    candidate is reliable rather than lucky, and a single attempt cannot say.
    """
    by_task: dict[str, list[sqlite3.Row]] = {}
    for row in members:
        by_task.setdefault(row["task_id"], []).append(row)
    repeated = [attempts for attempts in by_task.values() if len(attempts) >= 2]
    if not repeated:
        return None
    return sum(all(int(row["passed"]) for row in attempts) for attempts in repeated) / len(repeated)


def summarize_runs(members: Sequence[sqlite3.Row]) -> dict[str, Any]:
    attempts = len(members)
    if not attempts:
        raise BenchError("cannot summarize an empty run group")
    passed = sum(int(row["passed"]) for row in members)
    actual_total = sum(float(row["cost_total"]) for row in members)
    catalog_values = [row["catalog_cost_total"] for row in members]
    catalog_complete = all(value is not None for value in catalog_values)
    lower, upper = wilson_interval(passed, attempts)
    long_context = [row["long_context_requests"] for row in members if row["long_context_requests"] is not None]
    quality = [float(row["quality_score"]) for row in members if row["quality_score"] is not None]
    cache_ratios = [float(row["cache_hit_ratio"]) for row in members if row["cache_hit_ratio"] is not None]
    return {
        "attempts": attempts,
        "passed": passed,
        "pass_rate": passed / attempts,
        "ci": (lower, upper),
        "pass_pow_k": pass_power_k(members),
        "catalog_per_task": sum(float(value) for value in catalog_values) / attempts if catalog_complete else None,
        "actual_per_task": actual_total / attempts,
        "cost_per_pass": actual_total / passed if passed else None,
        "judge_cost_total": sum(float(row["judge_cost_total"] or 0.0) for row in members),
        "average_seconds": sum(float(row["duration_seconds"]) for row in members) / attempts,
        "average_quality": sum(quality) / len(quality) if quality else None,
        "average_cache_hit_ratio": sum(cache_ratios) / len(cache_ratios) if cache_ratios else None,
        "long_context_requests": sum(int(value) for value in long_context),
        "routing_mismatches": sum(not bool(row["configured_matches_actual"]) for row in members),
        "quota_per_task": quota_per_task(members),
    }


def format_quota(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.3f}%"


def row_class(row: sqlite3.Row, task_classes: Mapping[str, str]) -> str:
    """Class of one recorded run, backfilled from the task definition when absent.

    Rows written before task classes existed carry `''`, and their task still
    names a class, so the definition supplies it. A row whose task is gone from
    `tasks/` keeps whatever it recorded, which may be `''`; the report then
    counts it as having no class instead of inventing a weightless bucket.
    """
    return row["task_class"] or task_classes.get(row["task_id"], "")


def same_provider(candidate: str, judge_selector: str) -> bool:
    try:
        candidate_provider, _, _ = split_selector(split_candidate(candidate)[0])
        judge_provider, _, _ = split_selector(judge_selector)
    except BenchError:
        return False
    return candidate_provider == judge_provider


def group_self_judge(members: Sequence[sqlite3.Row]) -> bool | None:
    """Whether these runs were graded by a judge from the candidate's own provider.

    `None` means the question does not apply because no run in the group
    recorded a judge: a verify-only task and every row written before the judge
    column existed carry `''`.
    """
    judged = [row for row in members if row["judge"]]
    if not judged:
        return None
    return any(same_provider(row["candidate"], row["judge"]) for row in judged)


def candidate_label(candidate: str, self_judge: bool | None) -> str:
    return f"{candidate} (self-judge)" if self_judge else candidate


def command_score(args: argparse.Namespace) -> int:
    classes = load_classes()
    task_classes = {task.task_id: task.task_class for task in load_tasks(classes)}
    rows = fetch_rows(args.db.resolve())
    groups = group_rows(rows, ("task_id", "candidate"))
    output: list[dict[str, Any]] = []
    for (task_id, candidate), members in sorted(groups.items()):
        attempts = len(members)
        passed = sum(int(row["passed"]) for row in members)
        quality = [float(row["quality_score"]) for row in members if row["quality_score"] is not None]
        output.append(
            {
                "task": task_id,
                "class": row_class(members[0], task_classes),
                "candidate": candidate,
                "variant": split_candidate(candidate)[1],
                "attempts": attempts,
                "passed": passed,
                "pass_rate": passed / attempts,
                "quality_score": sum(quality) / len(quality) if quality else None,
                "actual_cost_total": sum(float(row["cost_total"]) for row in members),
                "judge_cost_total": sum(float(row["judge_cost_total"] or 0.0) for row in members),
                "quota_fraction_per_task": quota_per_task(members),
                "average_seconds": sum(float(row["duration_seconds"]) for row in members) / attempts,
            }
        )
    if args.format == "json":
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_table(
            (
                "Task",
                "Class",
                "Candidate",
                "Variant",
                "Pass",
                "Pass rate",
                "Quality",
                "Actual cost",
                "Quota/task",
                "Avg sec",
            ),
            [
                (
                    item["task"],
                    item["class"],
                    item["candidate"],
                    item["variant"] or "-",
                    f"{item['passed']}/{item['attempts']}",
                    format_rate(item["pass_rate"]),
                    format_quality(item["quality_score"]),
                    format_money(item["actual_cost_total"]),
                    format_quota(item["quota_fraction_per_task"]),
                    f"{item['average_seconds']:.1f}",
                )
                for item in output
            ],
        )
    return 0


def candidate_summaries(rows: Sequence[sqlite3.Row], minimum_samples: int) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for (candidate,), members in sorted(group_rows(rows, ("candidate",)).items()):
        summary = summarize_runs(members)
        summary["candidate"] = candidate
        summary["variant"] = split_candidate(candidate)[1]
        summary["self_judge"] = group_self_judge(members)
        summaries.append(summary)
    for summary in summaries:
        dominated_by: list[str] = []
        for other in summaries:
            if other is summary:
                continue
            quality_no_worse = other["pass_rate"] >= summary["pass_rate"]
            cost_no_worse = other["actual_per_task"] <= summary["actual_per_task"]
            strictly_better = (
                other["pass_rate"] > summary["pass_rate"]
                or other["actual_per_task"] < summary["actual_per_task"]
            )
            if quality_no_worse and cost_no_worse and strictly_better:
                dominated_by.append(other["candidate"])
        summary["status"] = "PARETO" if not dominated_by else "DOMINATED"
        summary["dominated_by"] = dominated_by
        summary["warning"] = f"LOW SAMPLE n<{minimum_samples}" if summary["attempts"] < minimum_samples else ""
    return summaries


def class_summaries(
    rows: Sequence[sqlite3.Row],
    classes: Mapping[str, TaskClass],
    task_classes: Mapping[str, str],
    minimum_samples: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[sqlite3.Row]]] = {}
    for row in rows:
        class_id = row_class(row, task_classes)
        if class_id not in classes:
            # A row whose class is unknown has no weight and no role to claim,
            # so it stays out of the per-class tables and out of the harness
            # score instead of being counted at weight zero.
            continue
        grouped.setdefault(class_id, {}).setdefault(row["candidate"], []).append(row)
    class_ids = sorted(classes, key=lambda class_id: (-classes[class_id].weight, class_id))
    summaries: list[dict[str, Any]] = []
    for class_id in class_ids:
        definition = classes[class_id]
        candidates: list[dict[str, Any]] = []
        subagent_observed = False
        for candidate, members in sorted(grouped.get(class_id, {}).items()):
            summary = summarize_runs(members)
            summary["candidate"] = candidate
            summary["variant"] = split_candidate(candidate)[1]
            summary["self_judge"] = group_self_judge(members)
            summary["low_sample"] = summary["attempts"] < minimum_samples
            candidates.append(summary)
            subagent_observed = subagent_observed or any(
                int(row["subagent_request_count"] or 0) > 0 for row in members
            )
        winner = pick_class_winner(candidates)
        summaries.append(
            {
                "class": class_id,
                "title": definition.title,
                "weight": definition.weight,
                "grading": definition.grading,
                "harness_roles": list(definition.harness_roles),
                "agent_overrides": list(definition.agent_overrides),
                "candidates": candidates,
                "recommended": winner["candidate"] if winner else None,
                "low_sample": bool(winner and winner["low_sample"]),
                "subagent_observed": subagent_observed,
            }
        )
    return summaries


def pick_class_winner(candidates: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Highest observed pass rate, then lowest actual cost per task, then name."""
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (-item["pass_rate"], item["actual_per_task"], item["candidate"]),
    )


def harness_scores(
    class_entries: Sequence[Mapping[str, Any]], classes: Mapping[str, TaskClass]
) -> list[dict[str, Any]]:
    """Weighted pass rate per candidate, counting a class with no data as zero."""
    observed: dict[str, dict[str, float]] = {}
    for entry in class_entries:
        if entry["class"] not in classes:
            continue
        for candidate in entry["candidates"]:
            observed.setdefault(candidate["candidate"], {})[entry["class"]] = candidate["pass_rate"]
    scores: list[dict[str, Any]] = []
    for candidate, per_class in sorted(observed.items()):
        score = sum(classes[class_id].weight * rate for class_id, rate in per_class.items())
        missing = sorted(set(classes) - set(per_class))
        scores.append(
            {
                "candidate": candidate,
                "score": score,
                "covered_weight": sum(classes[class_id].weight for class_id in per_class),
                "missing_classes": missing,
            }
        )
    scores.sort(key=lambda item: (-item["score"], item["candidate"]))
    return scores


def is_agy_candidate(candidate: str) -> bool:
    return split_candidate(candidate)[0].startswith(f"{AGY_PROVIDER}/")


def routing_recommendation(
    class_entries: Sequence[Mapping[str, Any]], classes: Mapping[str, TaskClass]
) -> dict[str, Any]:
    """Expand each class winner into the omp routing keys that class touches.

    Classes are resolved from the heaviest weight down, so the first class to
    claim a role keeps it and every later disagreement is reported as a
    conflict instead of silently overwriting the heavier class.

    An `agy/` winner never reaches the role map. OMP cannot resolve an
    Antigravity selector, and that candidate's actual cost is zero by
    construction, so it wins every cost tie-break without being comparable.
    The same rule is applied again over that class's OMP candidates to fill the
    role, and the agy winner is reported under `unroutable` together with the
    substitute. A class with no OMP candidate at all leaves its roles empty.

    A role other than `modelRoles.default`, and every agent override, is only
    recommended by a class whose recorded runs actually spawned a subagent.
    Nothing else in a run touches those keys, so a class without that
    observation has measured nothing about them: the key is reported under
    `unobserved` and left unclaimed, which lets a lighter class that did
    observe one fill it instead of freezing the key on no evidence. A class
    with no recorded run at all reports the same way, because "no run" is the
    strongest form of "nothing observed".

    `evidence` records, per claimed key, the class and the winning candidate,
    plus the samples, self-judging and low-sample state of the candidate
    summary whose selector is actually written. Those three read the
    substitute's own summary, not the agy winner's, because the substitute is
    what the proposal applies.
    """
    model_roles: dict[str, str] = {}
    agent_overrides: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    low_sample: list[str] = []
    variants: dict[str, str] = {}
    unroutable: list[dict[str, Any]] = []
    unobserved: list[dict[str, str]] = []
    evidence: dict[str, dict[str, Any]] = {}
    owners: dict[str, tuple[str, float, str]] = {}
    ordered = sorted(
        (entry for entry in class_entries if entry["class"] in classes),
        key=lambda entry: (-classes[entry["class"]].weight, entry["class"]),
    )
    for entry in ordered:
        class_id = entry["class"]
        definition = classes[class_id]
        keys = [f"{APPLY_ROLES_KEY}.{role}" for role in definition.harness_roles]
        keys += [f"{APPLY_OVERRIDES_KEY}.{name}" for name in definition.agent_overrides]
        subagent_keys = [key for key in keys if key != f"{APPLY_ROLES_KEY}.{MAIN_AGENT_ROLE}"]
        if not entry["subagent_observed"]:
            unobserved.extend({"key": key, "class": class_id} for key in subagent_keys)
        measured = pick_class_winner(entry["candidates"])
        if measured is None:
            continue
        winner = str(measured["candidate"])
        substituted = is_agy_candidate(winner)
        if substituted:
            measured = pick_class_winner(
                [item for item in entry["candidates"] if not is_agy_candidate(item["candidate"])]
            )
        applied = str(measured["candidate"]) if measured else ""
        selector, variant = split_candidate(applied) if applied else ("", "")
        if measured and measured["low_sample"]:
            low_sample.append(class_id)
        if variant:
            variants[class_id] = variant
        for key in keys:
            name = key.rsplit(".", 1)[1]
            target = model_roles if key.startswith(f"{APPLY_ROLES_KEY}.") else agent_overrides
            if key in subagent_keys and not entry["subagent_observed"]:
                continue
            owner = owners.get(key)
            if owner is None:
                owners[key] = (class_id, definition.weight, winner)
                if selector:
                    target[name] = selector
                evidence[key] = {
                    "class": class_id,
                    "candidate": winner,
                    "selector": selector or None,
                    "samples": int(measured["attempts"]) if measured else 0,
                    "self_judge": bool(measured["self_judge"]) if measured else False,
                    "variant": variant,
                    "low_sample": bool(measured["low_sample"]) if measured else False,
                }
                if substituted:
                    unroutable.append(
                        {
                            "key": key,
                            "class": class_id,
                            "candidate": winner,
                            "omp_fallback": applied or None,
                        }
                    )
                continue
            owner_class, owner_weight, owner_candidate = owner
            if owner_candidate == winner:
                continue
            conflicts.append(
                {
                    "key": key,
                    "winner": {"class": owner_class, "weight": owner_weight, "candidate": owner_candidate},
                    "loser": {"class": class_id, "weight": definition.weight, "candidate": winner},
                }
            )
    return {
        "modelRoles": model_roles,
        "agentModelOverrides": agent_overrides,
        "conflicts": conflicts,
        "low_sample": low_sample,
        "variants": variants,
        "unroutable": unroutable,
        "unobserved": unobserved,
        "evidence": evidence,
    }


@dataclass(frozen=True)
class ApplyScript:
    path: Path
    lines: tuple[bytes, ...]
    rows: dict[str, int]
    values: dict[str, dict[str, str]]


def load_apply_script(path: Path) -> ApplyScript:
    # The file is read and written as bytes so that every row outside the two
    # managed ones survives byte for byte, whatever its line ending is.
    try:
        lines = tuple(path.read_bytes().splitlines(keepends=True))
    except OSError as exc:
        raise BenchError(f"could not read {path}: {exc}") from exc
    rows: dict[str, int] = {}
    values: dict[str, dict[str, str]] = {}
    for index, line in enumerate(lines):
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            continue
        key, separator, raw = text.rstrip("\r\n").partition("|")
        if not separator or key not in APPLY_SETTING_KEYS:
            continue
        if key in rows:
            raise BenchError(f"{path} sets {key} on more than one row")
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BenchError(f"invalid JSON for {key} in {path}: {exc}") from exc
        if not isinstance(record, dict) or not all(
            isinstance(name, str) and isinstance(value, str) for name, value in record.items()
        ):
            raise BenchError(f"{key} in {path} must be an object of string values")
        rows[key] = index
        values[key] = record
    missing = [key for key in APPLY_SETTING_KEYS if key not in rows]
    if missing:
        raise BenchError(f"{path} has no managed row for {', '.join(missing)}")
    return ApplyScript(path=path, lines=lines, rows=rows, values=values)


def rewrite_apply_script(script: ApplyScript, proposal: Mapping[str, Mapping[str, str]]) -> bytes:
    lines = list(script.lines)
    for key, index in script.rows.items():
        body = lines[index].rstrip(b"\r\n")
        ending = lines[index][len(body) :]
        # Canonical JSON, exactly as apply.sh's own comparison renders it.
        value = json.dumps(proposal[key], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        lines[index] = f"{key}|{value}".encode("utf-8") + ending
    return b"".join(lines)


def write_apply_script(script: ApplyScript, updated: bytes) -> None:
    try:
        script.path.write_bytes(updated)
    except OSError as exc:
        raise BenchError(f"could not write {script.path}: {exc}") from exc


def changed_line_numbers(script: ApplyScript, updated: bytes) -> list[int]:
    after = updated.splitlines(keepends=True)
    return [
        index + 1 for index, line in enumerate(script.lines) if index >= len(after) or line != after[index]
    ]


def routing_proposal(
    current: Mapping[str, Mapping[str, str]], routing: Mapping[str, Any]
) -> dict[str, dict[str, str]]:
    """The managed records with recommended keys replaced and the rest kept.

    A key with no recommendation keeps its managed value, so a partial
    measurement never blanks a role the benchmark said nothing about.

    An agent override whose managed value is a role alias (`@mid`) keeps that
    alias when the recommendation is the very selector the alias resolves to
    under the proposed role map. Writing the literal selector there would look
    identical today and then stop following the role the next time that role
    changes, which is the opposite of what apply.sh's convention expresses.
    """
    roles = dict(current[APPLY_ROLES_KEY])
    roles.update(routing["modelRoles"])
    overrides = dict(current[APPLY_OVERRIDES_KEY])
    for name, selector in routing["agentModelOverrides"].items():
        alias = overrides.get(name, "")
        if alias.startswith(ROLE_ALIAS_PREFIX) and roles.get(alias[len(ROLE_ALIAS_PREFIX) :]) == selector:
            continue
        overrides[name] = selector
    return {APPLY_ROLES_KEY: roles, APPLY_OVERRIDES_KEY: overrides}


def routing_key_flags(key: str, routing: Mapping[str, Any]) -> list[str]:
    source = routing["evidence"].get(key)
    flags: list[str] = []
    if source:
        if source["low_sample"]:
            flags.append("(low-sample)")
        if source["self_judge"]:
            flags.append("(self-judge)")
        if source["variant"]:
            flags.append(f"variant:{source['variant']}")
    if any(item["key"] == key for item in routing["conflicts"]):
        flags.append("conflict")
    if any(item["key"] == key for item in routing["unroutable"]):
        flags.append("unroutable")
    return flags


def routing_changes(
    current: Mapping[str, Mapping[str, str]],
    proposal: Mapping[str, Mapping[str, str]],
    routing: Mapping[str, Any],
    variants: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Every managed key a human has to decide on: changed, or variant-bound.

    A recommendation that repeats the value already in apply.sh still needs a
    row when its candidate carried a variant. The value is identical, the
    measurement behind it is not, and the variant's overlay is the part a
    human has to apply or reject by hand.
    """
    changes: list[dict[str, Any]] = []
    for setting in APPLY_SETTING_KEYS:
        before = current[setting]
        after = proposal[setting]
        for name in sorted(set(before) | set(after)):
            key = f"{setting}.{name}"
            source = routing["evidence"].get(key)
            variant = source["variant"] if source else ""
            if before.get(name) == after.get(name) and not variant:
                continue
            change: dict[str, Any] = {
                "key": key,
                "from": before.get(name),
                "to": after.get(name),
                "class": source["class"] if source else None,
                "samples": source["samples"] if source else 0,
                "flags": routing_key_flags(key, routing),
            }
            if variant:
                change["variant_overlay"] = dict(variants.get(variant, {}))
            changes.append(change)
    return changes


def apply_script_diff(script: ApplyScript, updated: bytes) -> str:
    return "".join(
        difflib.unified_diff(
            [line.decode("utf-8", "replace") for line in script.lines],
            [line.decode("utf-8", "replace") for line in updated.splitlines(keepends=True)],
            fromfile=f"a/{script.path.name}",
            tofile=f"b/{script.path.name}",
            n=0,
        )
    )


def run_apply_check(path: Path) -> subprocess.CompletedProcess[str]:
    """Run apply.sh's report-only mode, which never calls `omp config set`."""
    try:
        return subprocess.run(
            ["bash", str(path), APPLY_CHECK_FLAG],
            capture_output=True,
            text=True,
            check=False,
            timeout=APPLY_CHECK_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise BenchError(f"{path} {APPLY_CHECK_FLAG} timed out") from exc
    except OSError as exc:
        raise BenchError(f"could not run {path} {APPLY_CHECK_FLAG}: {exc}") from exc


def apply_check_error(completed: subprocess.CompletedProcess[str], path: Path) -> str:
    """`''` when the check reported, a message when the script itself failed.

    That mode exits `0` when every managed value matches and `1` when some
    differ; both are reports about the file just written. Any other code means
    the script could not check (no `omp` on PATH, an unreadable setting), and
    a proposal that was never checked is not one a human should act on.
    """
    if completed.returncode in APPLY_CHECK_REPORT_CODES:
        return ""
    return (
        f"{path} {APPLY_CHECK_FLAG} failed with exit {completed.returncode}: "
        f"{abbreviated_output(completed) or 'no output'}"
    )


def print_candidate_table(summaries: Sequence[Mapping[str, Any]]) -> None:
    print("Candidate report (quality maximized, actual cost per task minimized)")
    print_table(
        (
            "Candidate",
            "Pass",
            "Pass rate (95% Wilson CI)",
            "Catalog est/task",
            "Actual/task",
            "Cost/pass",
            "Quota/task",
            "Avg sec",
            "Frontier",
            "Warning",
        ),
        [
            (
                candidate_label(summary["candidate"], summary["self_judge"]),
                f"{summary['passed']}/{summary['attempts']}",
                f"{format_rate(summary['pass_rate'])} ({format_rate(summary['ci'][0])}-{format_rate(summary['ci'][1])})",
                format_money(summary["catalog_per_task"]),
                format_money(summary["actual_per_task"]),
                format_money(summary["cost_per_pass"]),
                format_quota(summary["quota_per_task"]),
                f"{summary['average_seconds']:.1f}",
                summary["status"],
                summary["warning"],
            )
            for summary in summaries
        ],
    )


def print_class_tables(class_entries: Sequence[Mapping[str, Any]], unclassified: int) -> None:
    print()
    print("Per-class report (one table row per class and candidate)")
    rows: list[tuple[str, ...]] = []
    for entry in class_entries:
        for candidate in entry["candidates"]:
            rows.append(
                (
                    entry["class"],
                    f"{entry['weight']:.2f}" if entry["weight"] else "-",
                    candidate_label(candidate["candidate"], candidate["self_judge"]),
                    str(candidate["attempts"]),
                    f"{format_rate(candidate['pass_rate'])} "
                    f"({format_rate(candidate['ci'][0])}-{format_rate(candidate['ci'][1])})",
                    format_optional_rate(candidate["pass_pow_k"]),
                    format_quality(candidate["average_quality"]),
                    format_money(candidate["actual_per_task"]),
                    f"{candidate['average_seconds']:.1f}",
                    format_optional_rate(candidate["average_cache_hit_ratio"]),
                    str(candidate["long_context_requests"]),
                )
            )
    if rows:
        print_table(
            (
                "Class",
                "Weight",
                "Candidate",
                "Runs",
                "Pass rate (95% Wilson CI)",
                "pass^k",
                "Quality",
                "Actual/task",
                "Avg sec",
                "Cache hit",
                "Long-ctx reqs",
            ),
            rows,
        )
    else:
        print("No recorded run belongs to a defined class.")
    empty = [entry["class"] for entry in class_entries if not entry["candidates"]]
    if empty:
        print(f"Classes with no recorded run: {', '.join(empty)}")
    if unclassified:
        print(f"Rows with no defined class: {unclassified}")


def print_harness_scores(scores: Sequence[Mapping[str, Any]], self_judge: Mapping[str, bool | None]) -> None:
    print()
    print("Harness score (sum of class weight times that class's observed pass rate)")
    if not scores:
        print("No candidate has a run in any defined class.")
        return
    print_table(
        ("Candidate", "Harness score", "Covered weight", "Classes counted as zero"),
        [
            (
                candidate_label(score["candidate"], self_judge.get(score["candidate"])),
                f"{score['score']:.3f}",
                f"{score['covered_weight']:.2f}",
                ", ".join(score["missing_classes"]) or "none",
            )
            for score in scores
        ],
    )


def print_routing(routing: Mapping[str, Any], class_entries: Sequence[Mapping[str, Any]]) -> None:
    print()
    print("Routing recommendation (per class: highest observed pass rate, cheapest actual cost per task)")
    recommended = [entry for entry in class_entries if entry["recommended"]]
    if not recommended:
        print("No class has a recorded run, so no routing can be recommended.")
        return
    print_table(
        ("Class", "Weight", "Recommended candidate", "Roles", "Agent overrides", "Note"),
        [
            (
                entry["class"],
                f"{entry['weight']:.2f}" if entry["weight"] else "-",
                str(entry["recommended"]),
                ", ".join(entry["harness_roles"]) or "-",
                ", ".join(entry["agent_overrides"]) or "-",
                "(low-sample)" if entry["low_sample"] else "",
            )
            for entry in recommended
        ],
    )
    print(
        json.dumps(
            {"modelRoles": routing["modelRoles"], "task.agentModelOverrides": routing["agentModelOverrides"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    if routing["unobserved"]:
        print(
            "Unobserved note: no recorded run of these classes spawned a subagent, so the class measured "
            "nothing about the roles and agent overrides only a subagent reaches. Those keys are left out "
            "of the recommendation:"
        )
        print_unobserved(routing["unobserved"])
    if routing["variants"]:
        print(
            "Variant note: "
            + ", ".join(f"{class_id} recommends variant {name}" for class_id, name in routing["variants"].items())
            + ". A variant is an OMP config overlay, not a model selector, so it is reported here instead of"
            " being written into the role map."
        )
    if routing["unroutable"]:
        print(
            "Unroutable note: OMP cannot resolve an `agy/` selector, and that candidate's actual cost is "
            "zero by construction, so it wins the cost tie-break without being comparable. Its keys are "
            "filled from the best OMP candidate of the same class instead:"
        )
        for item in routing["unroutable"]:
            substitute = item["omp_fallback"] or "left empty (that class has no OMP candidate)"
            print(f"- {item['key']}: {item['class']} recommends {item['candidate']}, applied {substitute}")
    if routing["conflicts"]:
        print("Routing conflicts (the heavier class wins the key):")
        for conflict in routing["conflicts"]:
            winner = conflict["winner"]
            loser = conflict["loser"]
            print(
                f"- {conflict['key']}: {winner['candidate']} from {winner['class']} "
                f"(weight {winner['weight']:.2f}) beats {loser['candidate']} from {loser['class']} "
                f"(weight {loser['weight']:.2f})"
            )
    else:
        print("Routing conflicts: none")
    if routing["low_sample"]:
        print(f"Low-sample recommendations: {', '.join(routing['low_sample'])}")


def print_unobserved(unobserved: Sequence[Mapping[str, str]]) -> None:
    for item in unobserved:
        print(f"- {item['key']}: {item['class']} has no run with a subagent request")


def print_routing_proposal(
    script: ApplyScript,
    routing: Mapping[str, Any],
    proposal: Mapping[str, Mapping[str, str]],
    diff: str,
    variants: Mapping[str, Mapping[str, Any]],
) -> None:
    print(f"Routing proposal for {script.path}")
    keys = sorted(routing["evidence"], key=lambda key: (key.startswith(f"{APPLY_OVERRIDES_KEY}."), key))
    if keys:
        rows: list[tuple[str, ...]] = []
        for key in keys:
            setting, name = key.rsplit(".", 1)
            source = routing["evidence"][key]
            rows.append(
                (
                    key,
                    script.values[setting].get(name, "-"),
                    proposal[setting].get(name, "-"),
                    source["class"],
                    str(source["samples"]),
                    " ".join(routing_key_flags(key, routing)) or "-",
                )
            )
        print_table(("Key", "Current (apply.sh)", "Proposed", "Evidence class", "Samples", "Flags"), rows)
    else:
        print("No recorded class recommends a routing key.")
    for name in sorted(set(routing["variants"].values())):
        overlay = ", ".join(sorted(variants.get(name, {})))
        print(f"Variant {name} overlay keys (not applied by this proposal): {overlay or 'unknown variant'}")
    if routing["unobserved"]:
        print("Left out for want of a subagent observation:")
        print_unobserved(routing["unobserved"])
    for item in routing["unroutable"]:
        substitute = item["omp_fallback"] or "left empty (that class has no OMP candidate)"
        print(f"Unroutable {item['key']}: {item['class']} recommends {item['candidate']}, applied {substitute}")
    for conflict in routing["conflicts"]:
        winner = conflict["winner"]
        loser = conflict["loser"]
        print(
            f"Conflict {conflict['key']}: {winner['candidate']} from {winner['class']} "
            f"(weight {winner['weight']:.2f}) beats {loser['candidate']} from {loser['class']} "
            f"(weight {loser['weight']:.2f})"
        )
    if routing["low_sample"]:
        print(f"Low-sample recommendations: {', '.join(routing['low_sample'])}")
    print()
    if diff:
        print(diff, end="")
    else:
        print("No managed value changes: apply.sh already holds every recommended value.")


def command_routing(args: argparse.Namespace) -> int:
    config = load_config(DEFAULT_CONFIG)
    classes = load_classes()
    task_classes = {task.task_id: task.task_class for task in load_tasks(classes)}
    rows = fetch_rows(args.db.resolve())
    class_entries = class_summaries(rows, classes, task_classes, config["minimum_samples_warning"])
    routing = routing_recommendation(class_entries, classes)
    script = load_apply_script(args.apply_script.resolve())
    proposal = routing_proposal(script.values, routing)
    updated = rewrite_apply_script(script, proposal)
    document: dict[str, Any] = {
        "proposal": {key: proposal[key] for key in APPLY_SETTING_KEYS},
        "current": {key: script.values[key] for key in APPLY_SETTING_KEYS},
        "changes": routing_changes(script.values, proposal, routing, config["variants"]),
        "unobserved": routing["unobserved"],
        "unroutable": routing["unroutable"],
        "conflicts": routing["conflicts"],
        "low_sample": routing["low_sample"],
    }
    json_output = args.format == "json"
    if not json_output:
        print_routing_proposal(script, routing, proposal, apply_script_diff(script, updated), config["variants"])

    check_error = ""
    if args.write:
        write_apply_script(script, updated)
        completed = run_apply_check(script.path)
        check_error = apply_check_error(completed, script.path)
        output = "".join(stream for stream in (completed.stdout, completed.stderr) if stream)
        document["write"] = {
            "path": str(script.path),
            "changed_lines": changed_line_numbers(script, updated),
        }
        document["check"] = {"exit": completed.returncode, "output": output}
        message = f"wrote {script.path}"
        if json_output:
            print(message, file=sys.stderr)
        else:
            print(message)
            print(f"$ bash {script.path} {APPLY_CHECK_FLAG} (exit {completed.returncode})")
            if output:
                print(output, end="" if output.endswith("\n") else "\n")

    if json_output:
        print(json.dumps(document, ensure_ascii=False, indent=2))
    # A failed check is raised only after the document is on stdout: the write
    # happened and its result is part of the contract, even when the check
    # that follows could not run.
    if check_error:
        raise BenchError(check_error)
    return 0


def command_report(args: argparse.Namespace) -> int:
    config = load_config(args.config.resolve())
    classes = load_classes()
    task_classes = {task.task_id: task.task_class for task in load_tasks(classes)}
    minimum_samples = config["minimum_samples_warning"]
    rows = fetch_rows(args.db.resolve())
    summaries = candidate_summaries(rows, minimum_samples)
    class_entries = class_summaries(rows, classes, task_classes, minimum_samples)
    unclassified = sum(1 for row in rows if row_class(row, task_classes) not in classes)
    scores = harness_scores(class_entries, classes)
    routing = routing_recommendation(class_entries, classes)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "candidates": summaries,
                    "classes": class_entries,
                    "harness_score": scores,
                    "routing": routing,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print_candidate_table(summaries)
    pareto = [summary["candidate"] for summary in summaries if summary["status"] == "PARETO"]
    dominated = [summary for summary in summaries if summary["status"] == "DOMINATED"]
    print(f"Pareto frontier: {', '.join(pareto) if pareto else 'none'}")
    if any(summary["quota_per_task"] is not None for summary in summaries):
        print(
            "Quota note: an `agy/` candidate spends Antigravity plan quota, not money, so its "
            "USD columns are zero by construction and the frontier above cannot rank it against "
            "a paid candidate. Compare those rows on `Quota/task` instead."
        )
    if any(summary["self_judge"] for summary in summaries):
        judges = sorted({row["judge"] for row in rows if row["judge"]})
        print(
            f"Self-judge note: a row marked `(self-judge)` was graded by a judge from its own provider "
            f"({', '.join(judges)}), so its quality column is not an independent measurement."
        )
    judge_total = sum(summary["judge_cost_total"] for summary in summaries)
    if judge_total > 0:
        print(f"Judge cost recorded across these runs: {format_money(judge_total)} (excluded from candidate cost).")
    if dominated:
        print("Dominated candidates:")
        for summary in dominated:
            print(f"- {summary['candidate']} (dominated by {', '.join(summary['dominated_by'])})")
    else:
        print("Dominated candidates: none")

    print_class_tables(class_entries, unclassified)
    print_harness_scores(scores, {summary["candidate"]: summary["self_judge"] for summary in summaries})
    print_routing(routing, class_entries)

    mismatches = [row for row in rows if not bool(row["configured_matches_actual"])]
    print()
    if mismatches:
        print("Model routing mismatches:")
        for row in mismatches:
            print(
                f"- run {row['id']}: configured={row['candidate']} actual={row['actual_model']}:{row['actual_thinking']} "
                f"fallback={'yes' if row['fallback_used'] else 'no'}"
            )
    else:
        print("Model routing mismatches: none")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run or preview benchmark combinations")
    run_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="benchmark JSON configuration")
    run_parser.add_argument("--task", action="append", help="task id to run; repeat for multiple tasks")
    run_parser.add_argument(
        "--model",
        action="append",
        help="candidate to run as `<selector>` or `<selector>@<variant>`; repeat for multiple candidates",
    )
    run_parser.add_argument("--repeat", type=int, help="override each task's default repetition count")
    run_parser.add_argument("--budget-usd", type=float, help="maximum estimated/actual spend for this invocation")
    run_parser.add_argument("--judge", help="model selector for the rubric judge (default: config `judge`)")
    run_parser.add_argument("--dry-run", action="store_true", help="print combinations and estimates without calling OMP")
    run_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="result SQLite database")
    run_parser.set_defaults(handler=command_run)

    score_parser = subparsers.add_parser("score", help="summarize results by task and candidate")
    score_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="result SQLite database")
    score_parser.add_argument("--format", choices=("table", "json"), default="table")
    score_parser.set_defaults(handler=command_score)

    report_parser = subparsers.add_parser(
        "report", help="report candidate confidence intervals, per-class tables and routing recommendations"
    )
    report_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="benchmark JSON configuration")
    report_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="result SQLite database")
    report_parser.add_argument("--format", choices=("table", "json"), default="table")
    report_parser.set_defaults(handler=command_report)

    routing_parser = subparsers.add_parser(
        "routing", help="propose the apply.sh routing values that the recorded runs support"
    )
    routing_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="result SQLite database")
    routing_parser.add_argument(
        "--apply-script", type=Path, default=APPLY_SCRIPT, help="omp config apply script to propose against"
    )
    routing_parser.add_argument(
        "--write",
        action="store_true",
        help=f"rewrite the two managed routing rows, then run the script's {APPLY_CHECK_FLAG} mode",
    )
    routing_parser.add_argument("--format", choices=("text", "json"), default="text")
    routing_parser.set_defaults(handler=command_routing)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except BenchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
