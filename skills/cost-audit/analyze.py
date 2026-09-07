#!/usr/bin/env python3
"""Audit OMP session statistics for avoidable nominal token spend."""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sqlite3
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
FACTS_PATH = REPO_ROOT / "docs" / "FACTS.md"
STATS_PATH = Path.home() / ".omp" / "stats.db"
MODELS_PATH = Path.home() / ".omp" / "agent" / "models.db"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "var" / "audit"

DEFAULT_CONTEXT_THRESHOLD = 400_000
CACHE_REBUILD_THRESHOLD = 20_000
SHORT_CACHE_TTL_MINUTES = 5
LONG_CACHE_TTL_MINUTES = 60
# Catalog documentation multipliers. These are counterfactual estimates, not bills.
SHORT_CACHE_WRITE_PREMIUM_ESTIMATE = 1.25
LONG_CACHE_WRITE_PREMIUM_ESTIMATE = 2.0
CHARS_PER_TOKEN_ESTIMATE = 4
MARKDOWN_FINDINGS_LIMIT = 10
LOW_EFFORT_LEVELS = {"minimal", "low", "medium"}
ERROR_STOP_MARKERS = ("error", "abort", "fail", "timeout", "cancel")
NOTICE = (
    "Costs are nominal catalog-price equivalents for subscription accounts, "
    "not actual billed charges."
)

Message = dict[str, Any]
DetectorResult = dict[str, Any]


@dataclass
class AuditData:
    messages: list[Message]
    tool_calls: list[dict[str, Any]]
    prices: dict[tuple[str, str], dict[str, Any]]
    start_ms: int
    end_ms: int
    context_threshold: int
    filters: dict[str, Any]
    low_effort_segments: list[dict[str, Any]]
    compactions: list[dict[str, Any]]
    parse_warnings: list[str]


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def utc_iso(timestamp_ms: int) -> str:
    return (
        datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def parse_timestamp_ms(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def number(value: Any) -> float:
    return float(value or 0)


def integer(value: Any) -> int:
    return int(value or 0)


def percentile(sorted_values: list[int], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def distribution(values: list[int]) -> dict[str, float | int]:
    ordered = sorted(values)
    if not ordered:
        return {"mean": 0, "median": 0, "p90": 0, "p99": 0, "max": 0}
    return {
        "mean": round(statistics.fmean(ordered), 2),
        "median": round(statistics.median(ordered), 2),
        "p90": round(percentile(ordered, 0.90), 2),
        "p99": round(percentile(ordered, 0.99), 2),
        "max": ordered[-1],
    }


def context_tokens(row: Message) -> int:
    return (
        integer(row.get("input_tokens"))
        + integer(row.get("cache_read_tokens"))
        + integer(row.get("cache_write_tokens"))
    )


def open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def resolve_session_filter(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    expanded = Path(raw).expanduser()
    if "/" in raw or raw.endswith(".jsonl"):
        return "exact", str(expanded.resolve())
    return "contains", raw


def load_messages(
    connection: sqlite3.Connection,
    start_ms: int,
    end_ms: int,
    folder: str | None,
    session: str | None,
) -> list[Message]:
    inner_conditions: list[str] = []
    inner_parameters: list[Any] = []
    if folder:
        inner_conditions.append("folder LIKE ?")
        inner_parameters.append(f"%{folder}%")
    session_mode, session_value = resolve_session_filter(session)
    if session_mode == "exact":
        inner_conditions.append("session_file = ?")
        inner_parameters.append(session_value)
    elif session_mode == "contains":
        inner_conditions.append("session_file LIKE ?")
        inner_parameters.append(f"%{session_value}%")
    inner_where = " AND ".join(inner_conditions) if inner_conditions else "1 = 1"
    query = f"""
        WITH ordered AS (
            SELECT
                messages.*,
                LAG(timestamp) OVER (
                    PARTITION BY session_file ORDER BY timestamp, id
                ) AS previous_timestamp
            FROM messages
            WHERE {inner_where}
        )
        SELECT * FROM ordered
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY session_file, timestamp, id
    """
    parameters = [*inner_parameters, start_ms, end_ms]
    return [dict(row) for row in connection.execute(query, parameters)]


def load_tool_calls(
    connection: sqlite3.Connection,
    start_ms: int,
    end_ms: int,
    folder: str | None,
    session: str | None,
) -> list[dict[str, Any]]:
    conditions = ["timestamp >= ?", "timestamp <= ?"]
    parameters: list[Any] = [start_ms, end_ms]
    if folder:
        conditions.append("folder LIKE ?")
        parameters.append(f"%{folder}%")
    session_mode, session_value = resolve_session_filter(session)
    if session_mode == "exact":
        conditions.append("session_file = ?")
        parameters.append(session_value)
    elif session_mode == "contains":
        conditions.append("session_file LIKE ?")
        parameters.append(f"%{session_value}%")
    query = f"""
        SELECT * FROM tool_calls
        WHERE {' AND '.join(conditions)}
        ORDER BY session_file, timestamp, id
    """
    return [dict(row) for row in connection.execute(query, parameters)]


def load_prices(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Model catalog not found at {path}")
    prices: dict[tuple[str, str], dict[str, Any]] = {}
    with open_read_only(path) as connection:
        for row in connection.execute("SELECT provider_id, models FROM model_cache"):
            try:
                models = json.loads(row["models"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(models, list):
                continue
            for model in models:
                if not isinstance(model, dict) or not isinstance(model.get("cost"), dict):
                    continue
                model_id = model.get("id")
                if isinstance(model_id, str):
                    prices[(row["provider_id"], model_id)] = model["cost"]
    return prices


def rates_for_row(
    prices: dict[tuple[str, str], dict[str, Any]], row: Message
) -> dict[str, Any] | None:
    catalog = prices.get((str(row.get("provider", "")), str(row.get("model", ""))))
    if not catalog:
        return None
    long_context = catalog.get("longContext")
    if isinstance(long_context, dict):
        threshold = integer(long_context.get("inputThreshold"))
        if threshold and context_tokens(row) > threshold:
            return long_context
    return catalog


def counterfactual_cost(
    prices: dict[tuple[str, str], dict[str, Any]],
    row: Message,
    provider: str,
    model: str,
) -> float | None:
    target = dict(row)
    target["provider"] = provider
    target["model"] = model
    rates = rates_for_row(prices, target)
    if not rates:
        return None
    return (
        integer(row.get("input_tokens")) * number(rates.get("input"))
        + integer(row.get("output_tokens")) * number(rates.get("output"))
        + integer(row.get("cache_read_tokens")) * number(rates.get("cacheRead"))
        + integer(row.get("cache_write_tokens")) * number(rates.get("cacheWrite"))
    ) / 1_000_000




def parse_session_events(
    messages: list[Message], start_ms: int, end_ms: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    rows_by_entry = {
        (str(row["session_file"]), str(row["entry_id"])): row for row in messages
    }
    session_files = sorted({str(row["session_file"]) for row in messages})
    low_effort_segments: list[dict[str, Any]] = []
    compactions: list[dict[str, Any]] = []
    warnings: list[str] = []

    for session_file in session_files:
        path = Path(session_file)
        if not path.is_file():
            warnings.append(f"Session file is missing: {session_file}")
            continue
        thinking_level: str | None = None
        active_segment: dict[str, Any] | None = None

        def finish_segment() -> None:
            nonlocal active_segment
            if active_segment is not None:
                low_effort_segments.append(active_segment)
                active_segment = None

        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        warnings.append(
                            f"Invalid JSON at {session_file}:{line_number}; line skipped"
                        )
                        continue
                    entry_type = entry.get("type")
                    if entry_type == "thinking_level_change":
                        finish_segment()
                        level = entry.get("thinkingLevel")
                        thinking_level = level.lower() if isinstance(level, str) else None
                        continue
                    if entry_type == "model_change":
                        finish_segment()
                        continue
                    if entry_type == "compaction":
                        timestamp_ms = parse_timestamp_ms(entry.get("timestamp"))
                        if timestamp_ms is not None and start_ms <= timestamp_ms <= end_ms:
                            compactions.append(
                                {
                                    "session_file": session_file,
                                    "timestamp_ms": timestamp_ms,
                                    "timestamp": utc_iso(timestamp_ms),
                                    "tokens_before": integer(entry.get("tokensBefore")),
                                    "entry_id": entry.get("id"),
                                    "line": line_number,
                                }
                            )
                        continue
                    if entry_type != "message":
                        continue
                    nested_message = entry.get("message")
                    if not isinstance(nested_message, dict) or nested_message.get("role") != "assistant":
                        continue
                    row = rows_by_entry.get((session_file, str(entry.get("id"))))
                    if row is None:
                        continue
                    model = str(row.get("model", ""))
                    qualifies = model.startswith("claude-opus") and thinking_level in LOW_EFFORT_LEVELS
                    if not qualifies:
                        finish_segment()
                        continue
                    segment_key = (model, thinking_level)
                    if active_segment is None or active_segment["key"] != segment_key:
                        finish_segment()
                        active_segment = {
                            "key": segment_key,
                            "session_file": session_file,
                            "model": model,
                            "thinking_level": thinking_level,
                            "start_timestamp": utc_iso(integer(row["timestamp"])),
                            "end_timestamp": utc_iso(integer(row["timestamp"])),
                            "request_count": 0,
                            "total_tokens": 0,
                            "cost_usd": 0.0,
                            "entry_ids": [],
                        }
                    active_segment["request_count"] += 1
                    active_segment["total_tokens"] += integer(row.get("total_tokens"))
                    active_segment["cost_usd"] += number(row.get("cost_total"))
                    active_segment["end_timestamp"] = utc_iso(integer(row["timestamp"]))
                    if len(active_segment["entry_ids"]) < 3:
                        active_segment["entry_ids"].append(row.get("entry_id"))
            finish_segment()
        except OSError as error:
            warnings.append(f"Could not read {session_file}: {error}")

    return low_effort_segments, compactions, warnings


def make_result(
    detector_id: str,
    title: str,
    severity: str,
    findings: list[dict[str, Any]],
    estimated_usd: float,
    recommendation: str,
    details: dict[str, Any] | None = None,
) -> DetectorResult:
    return {
        "id": detector_id,
        "title": title,
        "severity": severity,
        "findings": findings,
        "estimated_usd": round(estimated_usd, 6),
        "recommendation": recommendation,
        "details": details or {},
    }


def detect_context_bloat(data: AuditData) -> DetectorResult:
    all_contexts = [context_tokens(row) for row in data.messages]
    oversized = [row for row in data.messages if context_tokens(row) > data.context_threshold]
    grouped: dict[str, list[Message]] = defaultdict(list)
    for row in oversized:
        grouped[str(row["session_file"])].append(row)
    findings: list[dict[str, Any]] = []
    for session_file, rows in grouped.items():
        largest = sorted(rows, key=context_tokens, reverse=True)[:3]
        findings.append(
            {
                "count": len(rows),
                "estimated_usd": round(sum(number(row.get("cost_cache_read")) for row in rows), 6),
                "summary": (
                    f"{Path(session_file).name}: {len(rows)} oversized requests; "
                    f"maximum context {max(context_tokens(row) for row in rows):,} tokens"
                ),
                "evidence": [
                    {
                        "session_file": session_file,
                        "entry_id": row.get("entry_id"),
                        "timestamp": utc_iso(integer(row["timestamp"])),
                        "context_tokens": context_tokens(row),
                        "cache_read_tokens": integer(row.get("cache_read_tokens")),
                        "cost_cache_read_usd": round(number(row.get("cost_cache_read")), 6),
                    }
                    for row in largest
                ],
            }
        )
    findings.sort(key=lambda item: item["estimated_usd"], reverse=True)
    estimated = sum(number(row.get("cost_cache_read")) for row in oversized)
    severity = "high" if oversized else "info"
    return make_result(
        "context_bloat",
        "Oversized request context",
        severity,
        findings,
        estimated,
        (
            f"Keep active context below {data.context_threshold:,} tokens by starting focused "
            "sessions, narrowing tool reads, and reviewing compaction.thresholdTokens."
        ),
        {
            "threshold_tokens": data.context_threshold,
            "request_count": len(oversized),
            "context_distribution_tokens": distribution(all_contexts),
            "attributed_cost": "sum(cost_cache_read) for requests above the threshold",
        },
    )


def detect_cache_rebuild(data: AuditData) -> DetectorResult:
    rebuilds = [
        row for row in data.messages if integer(row.get("cache_write_tokens")) > CACHE_REBUILD_THRESHOLD
    ]
    grouped: dict[str, list[Message]] = defaultdict(list)
    for row in rebuilds:
        grouped[str(row["session_file"])].append(row)

    findings: list[dict[str, Any]] = []
    for session_file, rows in grouped.items():
        evidence = []
        idle_5 = 0
        idle_60 = 0
        for row in sorted(rows, key=lambda item: number(item.get("cost_cache_write")), reverse=True):
            previous = row.get("previous_timestamp")
            gap_minutes = (
                (integer(row["timestamp"]) - integer(previous)) / 60_000 if previous is not None else None
            )
            if gap_minutes is not None and gap_minutes > SHORT_CACHE_TTL_MINUTES:
                idle_5 += 1
            if gap_minutes is not None and gap_minutes > LONG_CACHE_TTL_MINUTES:
                idle_60 += 1
            if len(evidence) < 5:
                evidence.append(
                    {
                        "session_file": session_file,
                        "entry_id": row.get("entry_id"),
                        "timestamp": utc_iso(integer(row["timestamp"])),
                        "gap_minutes": round(gap_minutes, 2) if gap_minutes is not None else None,
                        "cache_write_tokens": integer(row.get("cache_write_tokens")),
                        "cost_cache_write_usd": round(number(row.get("cost_cache_write")), 6),
                    }
                )
        findings.append(
            {
                "count": len(rows),
                "estimated_usd": round(sum(number(row.get("cost_cache_write")) for row in rows), 6),
                "summary": (
                    f"{Path(session_file).name}: {len(rows)} prefix rebuilds, "
                    f"{idle_5} after >5m idle and {idle_60} after >60m idle"
                ),
                "evidence": evidence,
            }
        )
    findings.sort(key=lambda item: item["estimated_usd"], reverse=True)

    over_5 = []
    five_to_60 = []
    over_60 = []
    unknown_gap_count = 0
    for row in rebuilds:
        previous = row.get("previous_timestamp")
        if previous is None:
            unknown_gap_count += 1
            continue
        gap = (integer(row["timestamp"]) - integer(previous)) / 60_000
        if gap > SHORT_CACHE_TTL_MINUTES:
            over_5.append(row)
        if SHORT_CACHE_TTL_MINUTES < gap <= LONG_CACHE_TTL_MINUTES:
            five_to_60.append(row)
        if gap > LONG_CACHE_TTL_MINUTES:
            over_60.append(row)

    rebuild_cost = sum(number(row.get("cost_cache_write")) for row in rebuilds)
    expired_5_cost = sum(number(row.get("cost_cache_write")) for row in over_5)
    recoverable_1h_cost = sum(number(row.get("cost_cache_write")) for row in five_to_60)
    expired_60_cost = sum(number(row.get("cost_cache_write")) for row in over_60)
    current_write_cost = sum(number(row.get("cost_cache_write")) for row in data.messages)
    premium_ratio = LONG_CACHE_WRITE_PREMIUM_ESTIMATE / SHORT_CACHE_WRITE_PREMIUM_ESTIMATE - 1
    extra_write_premium = current_write_cost * premium_ratio
    net = recoverable_1h_cost - extra_write_premium
    known_gap_count = len(rebuilds) - unknown_gap_count
    if net > 0:
        recommendation = (
            "The coarse estimate favors providers.cacheRetention: long; test it against auto "
            "and compare cache-write spend because the estimate cannot model provider eviction."
        )
    else:
        recommendation = (
            "Keep providers.cacheRetention: auto on this estimate; the projected 1-hour write "
            "premium exceeds rebuild savings. Reduce idle resumes or remeasure before changing it."
        )
    return make_result(
        "cache_rebuild",
        "Large cache prefix rebuilds",
        "high" if rebuilds else "info",
        findings,
        rebuild_cost,
        recommendation,
        {
            "threshold_cache_write_tokens": CACHE_REBUILD_THRESHOLD,
            "rebuild_count": len(rebuilds),
            "rebuild_cost_usd": round(rebuild_cost, 6),
            "median_rebuild_tokens": round(
                statistics.median([integer(row["cache_write_tokens"]) for row in rebuilds]), 2
            )
            if rebuilds
            else 0,
            "after_5m_count": len(over_5),
            "after_5m_percent_of_all": round(len(over_5) / len(rebuilds) * 100, 2)
            if rebuilds
            else 0,
            "after_5m_percent_of_known_gaps": round(len(over_5) / known_gap_count * 100, 2)
            if known_gap_count
            else 0,
            "after_5m_cost_usd": round(expired_5_cost, 6),
            "between_5m_and_60m_count": len(five_to_60),
            "between_5m_and_60m_cost_usd": round(recoverable_1h_cost, 6),
            "after_60m_count": len(over_60),
            "after_60m_cost_usd": round(expired_60_cost, 6),
            "unknown_previous_request_count": unknown_gap_count,
            "retention_estimate": {
                "five_minute_write_multiplier": SHORT_CACHE_WRITE_PREMIUM_ESTIMATE,
                "one_hour_write_multiplier": LONG_CACHE_WRITE_PREMIUM_ESTIMATE,
                "incremental_write_premium_usd": round(extra_write_premium, 6),
                "potential_5_to_60m_rebuild_savings_usd": round(recoverable_1h_cost, 6),
                "net_savings_usd": round(net, 6),
                "method": (
                    "Estimated: save observed >5m and <=60m rebuild writes, while applying the "
                    "2.0/1.25 premium delta to all observed cache-write cost."
                ),
            },
        },
    )


def detect_model_misroute(data: AuditData) -> DetectorResult:
    rows = [
        row
        for row in data.messages
        if row.get("agent_type") == "subagent" and str(row.get("model", "")).startswith("claude-opus")
    ]
    grouped: dict[str, list[Message]] = defaultdict(list)
    for row in rows:
        grouped[str(row["session_file"])].append(row)
    findings: list[dict[str, Any]] = []
    total_actual = 0.0
    total_luna = 0.0
    total_sol = 0.0
    unpriced = 0
    for session_file, group in grouped.items():
        actual = sum(number(row.get("cost_total")) for row in group)
        luna_values = [
            counterfactual_cost(data.prices, row, "openai-codex", "gpt-5.6-luna") for row in group
        ]
        sol_values = [
            counterfactual_cost(data.prices, row, "openai-codex", "gpt-5.6-sol") for row in group
        ]
        if any(value is None for value in luna_values + sol_values):
            unpriced += len(group)
        luna = sum(value or 0 for value in luna_values)
        sol = sum(value or 0 for value in sol_values)
        total_actual += actual
        total_luna += luna
        total_sol += sol
        evidence_rows = sorted(group, key=lambda row: number(row.get("cost_total")), reverse=True)[:3]
        findings.append(
            {
                "count": len(group),
                "estimated_usd": round(max(0.0, actual - luna), 6),
                "summary": (
                    f"{Path(session_file).name}: Opus ${actual:.4f}; "
                    f"Luna ${luna:.4f}; Sol ${sol:.4f}"
                ),
                "actual_opus_usd": round(actual, 6),
                "counterfactual_luna_usd": round(luna, 6),
                "counterfactual_sol_usd": round(sol, 6),
                "potential_savings_luna_usd": round(actual - luna, 6),
                "potential_savings_sol_usd": round(actual - sol, 6),
                "evidence": [
                    {
                        "session_file": session_file,
                        "entry_id": row.get("entry_id"),
                        "timestamp": utc_iso(integer(row["timestamp"])),
                        "model": row.get("model"),
                        "context_tokens": context_tokens(row),
                        "output_tokens": integer(row.get("output_tokens")),
                        "cost_total_usd": round(number(row.get("cost_total")), 6),
                    }
                    for row in evidence_rows
                ],
            }
        )
    findings.sort(key=lambda item: item["estimated_usd"], reverse=True)
    upper_bound_savings = max(0.0, total_actual - total_luna)
    return make_result(
        "model_misroute",
        "Subagents routed to an expensive model",
        "high" if rows else "info",
        findings,
        upper_bound_savings,
        (
            "Route lightweight agents through task.agentModelOverrides to @smol "
            "(modelRoles.smol) and general workers to @mid (modelRoles.mid)."
        ),
        {
            "request_count": len(rows),
            "session_file_count": len(grouped),
            "actual_opus_usd": round(total_actual, 6),
            "counterfactual_luna_usd": round(total_luna, 6),
            "counterfactual_sol_usd": round(total_sol, 6),
            "potential_savings_luna_usd": round(total_actual - total_luna, 6),
            "potential_savings_sol_usd": round(total_actual - total_sol, 6),
            "unpriced_request_count": unpriced,
            "pricing_source": str(MODELS_PATH),
            "role_attribution_limitation": (
                "stats.db identifies subagents but not their smol/mid role. Luna savings are an "
                "upper bound; Sol savings are a separate counterfactual and may be negative under "
                "long-context catalog tiers."
            ),
        },
    )


def detect_low_effort_expensive(data: AuditData) -> DetectorResult:
    findings = []
    for segment in data.low_effort_segments:
        findings.append(
            {
                "count": segment["request_count"],
                "estimated_usd": round(segment["cost_usd"], 6),
                "summary": (
                    f"{Path(segment['session_file']).name}: {segment['model']} "
                    f"at {segment['thinking_level']} for {segment['request_count']} requests"
                ),
                "evidence": [
                    {
                        "session_file": segment["session_file"],
                        "start_timestamp": segment["start_timestamp"],
                        "end_timestamp": segment["end_timestamp"],
                        "thinking_level": segment["thinking_level"],
                        "model": segment["model"],
                        "request_count": segment["request_count"],
                        "total_tokens": segment["total_tokens"],
                        "cost_total_usd": round(segment["cost_usd"], 6),
                        "entry_ids": segment["entry_ids"],
                    }
                ],
            }
        )
    findings.sort(key=lambda item: item["estimated_usd"], reverse=True)
    total_cost = sum(item["estimated_usd"] for item in findings)
    request_count = sum(item["count"] for item in findings)
    return make_result(
        "low_effort_expensive",
        "Expensive model at low or medium thinking effort",
        "high" if findings else "info",
        findings,
        total_cost,
        (
            "Use modelRoles.smol for low-effort work and reserve the Opus role for high-effort "
            "tasks. The supplied benchmark strictly dominates Opus low (58%, $1.66) with "
            "Luna max (67%, $0.61); it does not establish strict dominance for every medium segment."
        ),
        {
            "segment_count": len(findings),
            "request_count": request_count,
            "levels": sorted(LOW_EFFORT_LEVELS),
            "attributed_cost_usd": round(total_cost, 6),
            "benchmark_reason": "Opus low 58%/$1.66 is strictly dominated by Luna max 67%/$0.61.",
        },
    )


def build_replay_indexes(data: AuditData) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Message]] = defaultdict(list)
    for row in data.messages:
        grouped[str(row["session_file"])].append(row)
    indexes: dict[str, dict[str, Any]] = {}
    for session_file, rows in grouped.items():
        rows.sort(key=lambda row: (integer(row["timestamp"]), integer(row.get("id"))))
        timestamps = [integer(row["timestamp"]) for row in rows]
        rates = []
        for row in rows:
            catalog = rates_for_row(data.prices, row)
            rates.append(number(catalog.get("cacheRead")) if catalog else 0.0)
        suffix = [0.0] * (len(rates) + 1)
        for index in range(len(rates) - 1, -1, -1):
            suffix[index] = suffix[index + 1] + rates[index]
        indexes[session_file] = {
            "timestamps": timestamps,
            "suffix_cache_read_rates": suffix,
        }
    return indexes


def detect_fat_tool_result(data: AuditData) -> DetectorResult:
    replay_indexes = build_replay_indexes(data)
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "total_chars": 0,
            "approx_tokens": 0,
            "replay_requests": 0,
            "estimated_usd": 0.0,
            "calls": [],
        }
    )
    for call in data.tool_calls:
        result_chars = integer(call.get("result_chars"))
        if result_chars <= 0:
            continue
        session_file = str(call["session_file"])
        index = replay_indexes.get(session_file)
        replay_count = 0
        replay_rate_sum = 0.0
        if index:
            position = bisect.bisect_right(index["timestamps"], integer(call["timestamp"]))
            replay_count = len(index["timestamps"]) - position
            replay_rate_sum = index["suffix_cache_read_rates"][position]
        approximate_tokens = math.ceil(result_chars / CHARS_PER_TOKEN_ESTIMATE)
        estimated = approximate_tokens * replay_rate_sum / 1_000_000
        bucket = grouped[str(call.get("tool_name") or "unknown")]
        bucket["count"] += 1
        bucket["total_chars"] += result_chars
        bucket["approx_tokens"] += approximate_tokens
        bucket["replay_requests"] += replay_count
        bucket["estimated_usd"] += estimated
        bucket["calls"].append(
            {
                "session_file": session_file,
                "tool_call_id": call.get("tool_call_id"),
                "timestamp": utc_iso(integer(call["timestamp"])),
                "model": call.get("model"),
                "result_chars": result_chars,
                "approx_tokens": approximate_tokens,
                "subsequent_requests": replay_count,
                "estimated_replay_usd": round(estimated, 6),
            }
        )
    findings = []
    for tool_name, bucket in grouped.items():
        evidence = sorted(bucket["calls"], key=lambda item: item["result_chars"], reverse=True)[:5]
        findings.append(
            {
                "count": bucket["count"],
                "estimated_usd": round(bucket["estimated_usd"], 6),
                "summary": (
                    f"{tool_name}: {bucket['total_chars']:,} result characters across "
                    f"{bucket['count']:,} calls; {bucket['replay_requests']:,} downstream requests"
                ),
                "total_result_chars": bucket["total_chars"],
                "approx_result_tokens": bucket["approx_tokens"],
                "subsequent_request_count": bucket["replay_requests"],
                "evidence": evidence,
            }
        )
    findings.sort(key=lambda item: item["estimated_usd"], reverse=True)
    total_estimated = sum(item["estimated_usd"] for item in findings)
    return make_result(
        "fat_tool_result",
        "Large tool results replayed into later requests",
        "medium" if findings else "info",
        findings,
        total_estimated,
        (
            "Keep large tool output in files and read only required ranges; prefer narrow queries "
            "so repeated context does not carry unused results."
        ),
        {
            "tool_name_count": len(findings),
            "call_count": sum(item["count"] for item in findings),
            "estimated_replay_cost_usd": round(total_estimated, 6),
            "method": (
                f"Estimated at {CHARS_PER_TOKEN_ESTIMATE} characters/token and each later request's "
                "catalog cache-read rate. Characters are only a token proxy; compaction and prefix "
                "boundaries are not observable here, so this can overstate replay duration."
            ),
        },
    )


def is_error_row(row: Message) -> bool:
    if str(row.get("error_message") or "").strip():
        return True
    reason = str(row.get("stop_reason") or "").lower()
    return any(marker in reason for marker in ERROR_STOP_MARKERS)


def detect_error_and_retry_spend(data: AuditData) -> DetectorResult:
    error_rows = [row for row in data.messages if is_error_row(row)]
    grouped: dict[str, list[Message]] = defaultdict(list)
    for row in error_rows:
        message = str(row.get("error_message") or "").strip()
        key = message or f"stop_reason={row.get('stop_reason')}"
        grouped[key].append(row)
    findings = []
    for error_message, rows in grouped.items():
        evidence_rows = sorted(rows, key=lambda row: number(row.get("cost_total")), reverse=True)[:3]
        cost = sum(number(row.get("cost_total")) for row in rows)
        findings.append(
            {
                "count": len(rows),
                "estimated_usd": round(cost, 6),
                "summary": error_message,
                "evidence": [
                    {
                        "session_file": row.get("session_file"),
                        "entry_id": row.get("entry_id"),
                        "timestamp": utc_iso(integer(row["timestamp"])),
                        "stop_reason": row.get("stop_reason"),
                        "error_message": row.get("error_message"),
                        "total_tokens": integer(row.get("total_tokens")),
                        "cost_total_usd": round(number(row.get("cost_total")), 6),
                    }
                    for row in evidence_rows
                ],
            }
        )
    findings.sort(key=lambda item: (item["count"], item["estimated_usd"]), reverse=True)
    total_cost = sum(number(row.get("cost_total")) for row in error_rows)
    return make_result(
        "error_and_retry_spend",
        "Errors, aborts, and discarded request spend",
        "medium" if error_rows else "info",
        findings,
        total_cost,
        (
            "Separate provider overloads from user aborts, then review retry.fallbackChains for "
            "repeatable provider failures before increasing retry work."
        ),
        {
            "request_count": len(error_rows),
            "discarded_cost_usd": round(total_cost, 6),
            "distinct_error_count": len(findings),
        },
    )


def max_events_in_hour(timestamps: list[int]) -> int:
    maximum = 0
    left = 0
    for right, timestamp in enumerate(timestamps):
        while timestamp - timestamps[left] > 60 * 60 * 1000:
            left += 1
        maximum = max(maximum, right - left + 1)
    return maximum


def detect_compaction_churn(data: AuditData) -> DetectorResult:
    rows_by_session: dict[str, list[Message]] = defaultdict(list)
    for row in data.messages:
        rows_by_session[str(row["session_file"])].append(row)
    for rows in rows_by_session.values():
        rows.sort(key=lambda row: (integer(row["timestamp"]), integer(row.get("id"))))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for compaction in data.compactions:
        session_file = compaction["session_file"]
        rows = rows_by_session.get(session_file, [])
        timestamps = [integer(row["timestamp"]) for row in rows]
        position = bisect.bisect_right(timestamps, compaction["timestamp_ms"])
        following = rows[position] if position < len(rows) else None
        enriched = dict(compaction)
        enriched["following_cache_write_tokens"] = (
            integer(following.get("cache_write_tokens")) if following else 0
        )
        enriched["following_cache_write_usd"] = (
            round(number(following.get("cost_cache_write")), 6) if following else 0.0
        )
        enriched["following_entry_id"] = following.get("entry_id") if following else None
        grouped[session_file].append(enriched)

    findings = []
    for session_file, compactions in grouped.items():
        compactions.sort(key=lambda item: item["timestamp_ms"])
        timestamps = [item["timestamp_ms"] for item in compactions]
        peak = max_events_in_hour(timestamps)
        rebuild_cost = sum(number(item["following_cache_write_usd"]) for item in compactions)
        findings.append(
            {
                "count": len(compactions),
                "estimated_usd": round(rebuild_cost, 6),
                "priority_score": peak,
                "summary": (
                    f"{Path(session_file).name}: {len(compactions)} compactions; "
                    f"peak {peak} within 60m"
                ),
                "evidence": [
                    {
                        "session_file": session_file,
                        "timestamp": item["timestamp"],
                        "tokens_before": item["tokens_before"],
                        "following_entry_id": item["following_entry_id"],
                        "following_cache_write_tokens": item["following_cache_write_tokens"],
                        "following_cache_write_usd": item["following_cache_write_usd"],
                    }
                    for item in sorted(
                        compactions, key=lambda item: item["tokens_before"], reverse=True
                    )[:5]
                ],
            }
        )
    findings.sort(
        key=lambda item: (item["priority_score"], item["count"], item["estimated_usd"]),
        reverse=True,
    )
    total_cost = sum(item["estimated_usd"] for item in findings)
    peak = max((item["priority_score"] for item in findings), default=0)
    severity = "high" if peak >= 3 else "medium" if findings else "info"
    return make_result(
        "compaction_churn",
        "Repeated compaction and following cache rebuilds",
        severity,
        findings,
        total_cost,
        (
            "Inspect high-frequency sessions first and tune compaction.thresholdTokens only after "
            "comparing context-bloat cost with the following rebuild cost."
        ),
        {
            "compaction_count": len(data.compactions),
            "session_count": len(grouped),
            "following_rebuild_cost_usd": round(total_cost, 6),
            "peak_compactions_within_60m": peak,
            "limitation": (
                "Compaction entries record tokensBefore but not post-compaction tokens; savings "
                "and compression ratio cannot be calculated."
            ),
        },
    )


def detect_idle_session_resume(data: AuditData) -> DetectorResult:
    idle_rows = []
    for row in data.messages:
        previous = row.get("previous_timestamp")
        if previous is None:
            continue
        gap_minutes = (integer(row["timestamp"]) - integer(previous)) / 60_000
        if gap_minutes > LONG_CACHE_TTL_MINUTES:
            enriched = dict(row)
            enriched["gap_minutes"] = gap_minutes
            idle_rows.append(enriched)
    grouped: dict[str, list[Message]] = defaultdict(list)
    for row in idle_rows:
        grouped[str(row["session_file"])].append(row)
    findings = []
    for session_file, rows in grouped.items():
        cost = sum(number(row.get("cost_cache_write")) for row in rows)
        evidence_rows = sorted(rows, key=lambda row: row["gap_minutes"], reverse=True)[:5]
        findings.append(
            {
                "count": len(rows),
                "estimated_usd": round(cost, 6),
                "summary": (
                    f"{Path(session_file).name}: {len(rows)} resumes after >60m; "
                    f"${cost:.4f} cache writes at resume"
                ),
                "evidence": [
                    {
                        "session_file": session_file,
                        "entry_id": row.get("entry_id"),
                        "timestamp": utc_iso(integer(row["timestamp"])),
                        "gap_minutes": round(row["gap_minutes"], 2),
                        "cache_write_tokens": integer(row.get("cache_write_tokens")),
                        "cost_cache_write_usd": round(number(row.get("cost_cache_write")), 6),
                    }
                    for row in evidence_rows
                ],
            }
        )
    findings.sort(key=lambda item: item["estimated_usd"], reverse=True)
    total_cost = sum(number(row.get("cost_cache_write")) for row in idle_rows)
    return make_result(
        "idle_session_resume",
        "Session resumes after more than one hour idle",
        "medium" if idle_rows else "info",
        findings,
        total_cost,
        (
            "Start a fresh focused session after long idle periods when old conversation state is "
            "not required; retain the old session only when its context is worth the rebuild."
        ),
        {
            "idle_threshold_minutes": LONG_CACHE_TTL_MINUTES,
            "resume_count": len(idle_rows),
            "resume_cache_write_cost_usd": round(total_cost, 6),
        },
    )


DETECTORS: list[Callable[[AuditData], DetectorResult]] = [
    detect_context_bloat,
    detect_cache_rebuild,
    detect_model_misroute,
    detect_low_effort_expensive,
    detect_fat_tool_result,
    detect_error_and_retry_spend,
    detect_compaction_churn,
    detect_idle_session_resume,
]


def build_baseline(data: AuditData) -> dict[str, Any]:
    request_count = len(data.messages)
    costs = {
        "input": sum(number(row.get("cost_input")) for row in data.messages),
        "output": sum(number(row.get("cost_output")) for row in data.messages),
        "cache_read": sum(number(row.get("cost_cache_read")) for row in data.messages),
        "cache_write": sum(number(row.get("cost_cache_write")) for row in data.messages),
    }
    total_cost = sum(number(row.get("cost_total")) for row in data.messages)
    context_total = sum(context_tokens(row) for row in data.messages)
    cache_read_tokens = sum(integer(row.get("cache_read_tokens")) for row in data.messages)
    model_groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"requests": 0, "nominal_cost_usd": 0.0}
    )
    agent_groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"requests": 0, "nominal_cost_usd": 0.0}
    )
    for row in data.messages:
        model = str(row.get("model") or "unknown")
        model_groups[model]["requests"] += 1
        model_groups[model]["nominal_cost_usd"] += number(row.get("cost_total"))
        agent_type = str(row.get("agent_type") or "unknown")
        agent_groups[agent_type]["requests"] += 1
        agent_groups[agent_type]["nominal_cost_usd"] += number(row.get("cost_total"))
    for groups in (model_groups, agent_groups):
        for values in groups.values():
            values["nominal_cost_usd"] = round(values["nominal_cost_usd"], 6)
            values["cost_percent"] = round(
                values["nominal_cost_usd"] / total_cost * 100, 2
            ) if total_cost else 0.0
    cost_composition = {
        name: {
            "nominal_cost_usd": round(value, 6),
            "percent": round(value / total_cost * 100, 2) if total_cost else 0.0,
        }
        for name, value in costs.items()
    }
    return {
        "period": {
            "start": utc_iso(data.start_ms),
            "end": utc_iso(data.end_ms),
            "days": round((data.end_ms - data.start_ms) / 86_400_000, 4),
        },
        "filters": data.filters,
        "request_count": request_count,
        "total_tokens": sum(integer(row.get("total_tokens")) for row in data.messages),
        "nominal_cost_usd": round(total_cost, 6),
        "model_spend": dict(
            sorted(model_groups.items(), key=lambda item: item[1]["nominal_cost_usd"], reverse=True)
        ),
        "cost_composition": cost_composition,
        "cache_hit_rate_percent": round(
            cache_read_tokens / context_total * 100, 2
        ) if context_total else 0.0,
        "context_distribution_tokens": distribution(
            [context_tokens(row) for row in data.messages]
        ),
        "agent_type_spend": dict(
            sorted(agent_groups.items(), key=lambda item: item[1]["nominal_cost_usd"], reverse=True)
        ),
    }


def format_integer(value: Any) -> str:
    return f"{integer(value):,}"


def format_money(value: Any) -> str:
    amount = number(value)
    return f"${amount:,.4f}" if abs(amount) < 100 else f"${amount:,.2f}"


def markdown_escape(value: Any) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text if len(text) <= 320 else text[:317] + "..."


def detail_text(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={detail_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(detail_text(item) for item in value)
    if isinstance(value, float):
        return f"{value:,.6f}".rstrip("0").rstrip(".")
    return str(value)


def evidence_text(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "No per-request evidence"
    item = evidence[0]
    return "; ".join(f"{key}={detail_text(value)}" for key, value in item.items())


def render_baseline_markdown(baseline: dict[str, Any]) -> list[str]:
    period = baseline["period"]
    contexts = baseline["context_distribution_tokens"]
    lines = [
        "## Baseline",
        "",
        f"- Period: `{period['start']}` to `{period['end']}` ({period['days']} days)",
        f"- Requests: **{format_integer(baseline['request_count'])}**",
        f"- Total tokens: **{format_integer(baseline['total_tokens'])}**",
        f"- Nominal spend: **{format_money(baseline['nominal_cost_usd'])}**",
        f"- Cache hit rate: **{baseline['cache_hit_rate_percent']:.2f}%**",
        (
            "- Context/request: mean {mean}, median {median}, p90 {p90}, p99 {p99}, "
            "max {max} tokens"
        ).format(**{key: format_integer(value) for key, value in contexts.items()}),
    ]
    filters = baseline.get("filters", {})
    active_filters = [f"{key}={value}" for key, value in filters.items() if value is not None]
    if active_filters:
        lines.append(f"- Filters: `{markdown_escape(', '.join(active_filters))}`")
    lines.extend(
        [
            "",
            "### Model spend",
            "",
            "| Model | Requests | Nominal spend | Share |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for model, values in baseline["model_spend"].items():
        lines.append(
            f"| {markdown_escape(model)} | {format_integer(values['requests'])} | "
            f"{format_money(values['nominal_cost_usd'])} | {values['cost_percent']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "### Cost composition",
            "",
            "| Component | Nominal spend | Share |",
            "| --- | ---: | ---: |",
        ]
    )
    for component, values in baseline["cost_composition"].items():
        lines.append(
            f"| {component} | {format_money(values['nominal_cost_usd'])} | "
            f"{values['percent']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "### Main vs. subagent",
            "",
            "| Agent type | Requests | Nominal spend | Share |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for agent_type, values in baseline["agent_type_spend"].items():
        lines.append(
            f"| {markdown_escape(agent_type)} | {format_integer(values['requests'])} | "
            f"{format_money(values['nominal_cost_usd'])} | {values['cost_percent']:.2f}% |"
        )
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# OMP Cost Audit",
        "",
        f"> **Caution:** {NOTICE}",
        "",
        f"Generated at `{report['generated_at']}`.",
        "",
        *render_baseline_markdown(report["baseline"]),
    ]
    detectors = report.get("detectors", [])
    if detectors:
        lines.extend(["", "## Detectors"])
    for result in detectors:
        lines.extend(
            [
                "",
                f"### {result['title']} (`{result['id']}`, {result['severity']})",
                "",
                f"- Attributed or potential amount: **{format_money(result['estimated_usd'])}**",
                f"- Recommendation: {result['recommendation']}",
            ]
        )
        for key, value in result.get("details", {}).items():
            lines.append(f"- {key.replace('_', ' ').title()}: {markdown_escape(detail_text(value))}")
        findings = result.get("findings", [])
        if not findings:
            lines.extend(["", "No findings in the selected period."])
            continue
        displayed = findings[:MARKDOWN_FINDINGS_LIMIT]
        lines.extend(
            [
                "",
                f"Top findings (showing {len(displayed)} of {len(findings)}; JSON contains all):",
                "",
                "| # | Cases | Amount | Summary | Evidence |",
                "| ---: | ---: | ---: | --- | --- |",
            ]
        )
        for index, finding in enumerate(displayed, start=1):
            lines.append(
                f"| {index} | {format_integer(finding.get('count'))} | "
                f"{format_money(finding.get('estimated_usd'))} | "
                f"{markdown_escape(finding.get('summary', ''))} | "
                f"{markdown_escape(evidence_text(finding.get('evidence', [])))} |"
            )
    limitations = report.get("limitations", [])
    if limitations:
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {item}" for item in limitations)
    return "\n".join(lines) + "\n"


def resolve_output_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    if path.parent == Path("."):
        return DEFAULT_OUTPUT_DIR / path
    return REPO_ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=positive_int, default=7, help="lookback days (default: 7)")
    parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown", help="report format"
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        help=(
            "write to PATH instead of stdout; a bare filename is placed under "
            "the repository's var/audit directory"
        ),
    )
    parser.add_argument("--folder", help="only rows whose project folder contains this value")
    parser.add_argument(
        "--session", help="only one exact JSONL path or session-id prefix/substring"
    )
    parser.add_argument(
        "--baseline", action="store_true", help="recalculate and print only the baseline"
    )
    parser.add_argument(
        "--ctx-threshold",
        type=positive_int,
        default=DEFAULT_CONTEXT_THRESHOLD,
        help=f"context-bloat threshold in tokens (default: {DEFAULT_CONTEXT_THRESHOLD})",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not FACTS_PATH.is_file():
        raise RuntimeError(
            f"Repository root could not be verified: expected {FACTS_PATH}"
        )
    if not STATS_PATH.is_file():
        raise RuntimeError(
            f"OMP statistics database not found at {STATS_PATH}. Run 'omp stats --summary' first."
        )
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - args.days * 86_400_000
    try:
        with open_read_only(STATS_PATH) as connection:
            messages = load_messages(
                connection, start_ms, end_ms, args.folder, args.session
            )
            tool_calls = (
                []
                if args.baseline
                else load_tool_calls(
                    connection, start_ms, end_ms, args.folder, args.session
                )
            )
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not read OMP statistics at {STATS_PATH}: {error}") from error
    if not messages:
        raise RuntimeError(
            "No OMP request rows matched the selected period and filters. "
            "Run 'omp stats --summary' to synchronize statistics, then retry."
        )
    prices = {} if args.baseline else load_prices(MODELS_PATH)
    low_effort_segments: list[dict[str, Any]] = []
    compactions: list[dict[str, Any]] = []
    parse_warnings: list[str] = []
    if not args.baseline:
        low_effort_segments, compactions, parse_warnings = parse_session_events(
            messages, start_ms, end_ms
        )
    data = AuditData(
        messages=messages,
        tool_calls=tool_calls,
        prices=prices,
        start_ms=start_ms,
        end_ms=end_ms,
        context_threshold=args.ctx_threshold,
        filters={"folder": args.folder, "session": args.session},
        low_effort_segments=low_effort_segments,
        compactions=compactions,
        parse_warnings=parse_warnings,
    )
    detectors = [] if args.baseline else [detector(data) for detector in DETECTORS]
    return {
        "schema_version": 1,
        "mode": "baseline" if args.baseline else "audit",
        "generated_at": utc_iso(end_ms),
        "notice": NOTICE,
        "baseline": build_baseline(data),
        "detectors": detectors,
        "limitations": [
            "Catalog-equivalent costs do not represent the subscription invoice.",
            (
                f"Tool result tokens use a {CHARS_PER_TOKEN_ESTIMATE}-characters-per-token proxy; "
                "actual tokenization and replay boundaries are unavailable."
            ),
            "Compaction records expose tokensBefore but not post-compaction token counts.",
            *parse_warnings,
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run(args)
        output = (
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else render_markdown(report)
        )
        if args.out:
            output_path = resolve_output_path(args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
            print(f"Wrote {output_path}", file=sys.stderr)
        else:
            sys.stdout.write(output)
        return 0
    except (RuntimeError, OSError, ValueError) as error:
        print(f"cost-audit: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
