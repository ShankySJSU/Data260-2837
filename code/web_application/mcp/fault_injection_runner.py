import csv
import json
import time
from pathlib import Path


from retry_utils import (
    RetryPolicy,
    SeededFaultInjector,
    call_with_retry,
)


# ============================================================
# CONFIGURATION
# ============================================================

VERIFY_SEED = 262837

FAILURE_RATES = [
    0.0,
    0.20,
    0.50,
]

CALLS_PER_RATE = 50

POLICY = RetryPolicy(
    timeout_seconds=1.0,
    max_attempts=3,
    base_delay_seconds=0.005,
    max_delay_seconds=0.02,
)


# ============================================================
# OUTPUT PATHS
# ============================================================

REPO_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = (
    REPO_ROOT
    / "reports"
    / "hw05"
    / "raw"
)

RAW_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

CSV_OUTPUT = (
    RAW_DIR
    / "fault_injection_calls.csv"
)

SUMMARY_OUTPUT = (
    RAW_DIR
    / "fault_injection_summary.json"
)

DEMO_OUTPUT = (
    RAW_DIR
    / "retry_demonstration.json"
)

METRICS_OUTPUT = (
    REPO_ROOT
    / "reports"
    / "hw05"
    / "part3_metrics.md"
)


# ============================================================
# DEMO OPERATION
# ============================================================

def simulated_operation():
    """
    Simulates a successful storage/API operation.
    """
    time.sleep(0.001)

    return {
        "message": "simulated operation succeeded"
    }


# ============================================================
# PERCENTILE CALCULATION
# ============================================================

def percentile(
    values: list[float],
    percentage: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    position = (
        (len(ordered) - 1)
        * percentage
        / 100
    )

    lower = int(position)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = position - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


# ============================================================
# SCRIPTED RETRY DEMONSTRATION
# ============================================================

class ScriptedInjector:
    """
    Deterministic injector used to demonstrate:
    1. First-attempt success.
    2. First failure followed by success.
    3. Failure after all retries.
    """

    def __init__(
        self,
        decisions: list[bool],
    ):
        self.decisions = decisions
        self.position = 0

    def should_fail(self) -> bool:
        if self.position >= len(self.decisions):
            return False

        decision = self.decisions[self.position]
        self.position += 1

        return decision


def run_retry_demonstration():
    demonstrations = []

    examples = [
        (
            "success_on_first_attempt",
            [False],
        ),
        (
            "failure_then_success_after_retry",
            [True, False],
        ),
        (
            "failure_after_all_allowed_retries",
            [True, True, True],
        ),
    ]

    for name, decisions in examples:
        injector = ScriptedInjector(decisions)

        result = call_with_retry(
            operation=simulated_operation,
            injector=injector,
            policy=POLICY,
        )

        demonstrations.append(
            {
                "scenario": name,
                "success": result.success,
                "attempts": result.attempts,
                "latency_ms": round(
                    result.latency_ms,
                    3,
                ),
                "error": result.error,
            }
        )

        print(
            f"{name}: "
            f"success={result.success}, "
            f"attempts={result.attempts}, "
            f"error={result.error}"
        )

    with DEMO_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            demonstrations,
            file,
            indent=2,
        )

    return demonstrations


# ============================================================
# 150-CALL FAULT-INJECTION EXPERIMENT
# ============================================================

def run_fault_experiment():
    rows = []
    summaries = []

    for failure_rate in FAILURE_RATES:
        print(
            f"\nRunning failure rate "
            f"{failure_rate:.0%}..."
        )

        # Same seed for reproducible results.
        injector = SeededFaultInjector(
            seed=VERIFY_SEED,
            failure_rate=failure_rate,
        )

        rate_results = []

        for call_number in range(
            1,
            CALLS_PER_RATE + 1,
        ):
            result = call_with_retry(
                operation=simulated_operation,
                injector=injector,
                policy=POLICY,
            )

            row = {
                "seed": VERIFY_SEED,
                "failure_rate": failure_rate,
                "call_number": call_number,
                "success": result.success,
                "attempts": result.attempts,
                "latency_ms": round(
                    result.latency_ms,
                    3,
                ),
                "error": result.error or "",
            }

            rows.append(row)
            rate_results.append(row)

        latencies = [
            row["latency_ms"]
            for row in rate_results
        ]

        successes = [
            row
            for row in rate_results
            if row["success"]
        ]

        success_rate = (
            len(successes)
            / CALLS_PER_RATE
            * 100
        )

        summary = {
            "seed": VERIFY_SEED,
            "failure_rate": failure_rate,
            "total_calls": CALLS_PER_RATE,
            "successful_calls": len(successes),
            "failed_calls": (
                CALLS_PER_RATE
                - len(successes)
            ),
            "success_rate_percent": round(
                success_rate,
                2,
            ),
            "mean_latency_ms": round(
                sum(latencies)
                / len(latencies),
                3,
            ),
            "p99_latency_ms": round(
                percentile(latencies, 99),
                3,
            ),
        }

        summaries.append(summary)

        print(
            f"success rate="
            f"{summary['success_rate_percent']}%, "
            f"mean="
            f"{summary['mean_latency_ms']} ms, "
            f"p99="
            f"{summary['p99_latency_ms']} ms"
        )

    # Save all 150 raw call records.
    with CSV_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        fieldnames = [
            "seed",
            "failure_rate",
            "call_number",
            "success",
            "attempts",
            "latency_ms",
            "error",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    # Save summary JSON.
    with SUMMARY_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            summaries,
            file,
            indent=2,
        )

    return summaries


# ============================================================
# METRICS MARKDOWN
# ============================================================

def write_metrics_markdown(
    summaries,
):
    lines = [
        "# DATA260 HW5 Part 3 Metrics",
        "",
        f"- VERIFY_SEED: `{VERIFY_SEED}`",
        f"- Calls per failure rate: `{CALLS_PER_RATE}`",
        f"- Total calls: `{CALLS_PER_RATE * len(FAILURE_RATES)}`",
        f"- Maximum attempts: `{POLICY.max_attempts}`",
        f"- Timeout per attempt: `{POLICY.timeout_seconds}` seconds",
        f"- Base backoff delay: `{POLICY.base_delay_seconds}` seconds",
        f"- Maximum backoff delay: `{POLICY.max_delay_seconds}` seconds",
        "",
        "| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |",
        "|---:|---:|---:|---:|",
    ]

    for summary in summaries:
        lines.append(
            "| "
            f"{summary['failure_rate']:.0%} | "
            f"{summary['success_rate_percent']:.2f}% | "
            f"{summary['mean_latency_ms']:.3f} | "
            f"{summary['p99_latency_ms']:.3f} |"
        )

    lines.extend(
        [
            "",
            "## Retry demonstration",
            "",
            "The retry policy demonstrates three cases:",
            "",
            "1. Success on the first attempt.",
            "2. Failure on the first attempt followed by success after retry.",
            "3. Failure after all allowed retry attempts.",
            "",
            "Raw call records are stored in:",
            "",
            "`reports/hw05/raw/fault_injection_calls.csv`",
            "",
            "Summary results are stored in:",
            "",
            "`reports/hw05/raw/fault_injection_summary.json`",
        ]
    )

    METRICS_OUTPUT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("Running retry demonstrations...")
    run_retry_demonstration()

    print("\nRunning 150-call fault experiment...")
    summaries = run_fault_experiment()

    write_metrics_markdown(summaries)

    print("\nPart 3 experiment completed.")
    print(f"Raw calls: {CSV_OUTPUT}")
    print(f"Summary: {SUMMARY_OUTPUT}")
    print(f"Metrics: {METRICS_OUTPUT}")