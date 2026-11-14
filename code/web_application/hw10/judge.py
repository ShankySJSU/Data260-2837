"""HW10 Parts 2 and 3 - the automated judge: GEval (DeepEval) on a LOCAL Ollama model.

Judge settings (documented in every result file through Judge.describe()):
    framework    deepeval GEval, explicit evaluation_steps + rubric, async_mode=False
    model        Ollama qwen3:4b (HW10_JUDGE_MODEL), http://localhost:11434, think=False
    sampling     temperature 0, seed 2837
    scale        1-5 (1 very poor ... 5 excellent). GEval scores 0-10 internally and reports
                 0-1; the rubric splits 0-10 into five bands and to_1_5() maps the band to 1-5.

Bounds: every Ollama call has an HTTP timeout, every GEval measure() runs under a hard
wall-clock limit, invalid inputs are rejected without calling the model, and after 3
consecutive failures the judge is declared unavailable so a run can never hang.

HW10_JUDGE=mock replaces the model with a deterministic heuristic - OFFLINE SMOKE TEST ONLY.
"""

import concurrent.futures
import json
import os
import re
import time

import requests

from . import config as cfg
from .common import log

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")  # no network calls from deepeval
os.environ.setdefault("ERROR_REPORTING", "NO")

COMPONENT = "JUDGE"

# 0-10 GEval band -> 1-5 label (inclusive, non-overlapping, covers 0-10)
BANDS = [((0, 2), 1), ((3, 4), 2), ((5, 6), 3), ((7, 8), 4), ((9, 10), 5)]

CRITERIA = {
    "plan_quality": {
        "name": "Plan Quality",
        "steps": [
            "Read the user question in the input. It may contain database facts about a "
            "restaurant inspection and the county policy.",
            "Check whether the plan steps in the actual output are specific to this question "
            "(the restaurant, fact or rule that is needed) instead of generic advice.",
            "Check whether the steps are in a logical order and whether a writer who follows "
            "them would produce a complete and correct answer to the question.",
            "Penalize steps that are irrelevant, repeated, or that lead away from the facts "
            "given in the input.",
        ],
        "outcomes": {
            1: "Very poor: the plan is unrelated to the question or unusable.",
            2: "Poor: mostly generic or misdirected; following it would miss the question.",
            3: "Acceptable: addresses the question but with generic, missing or disordered steps.",
            4: "Good: specific and ordered, with only minor gaps or redundancy.",
            5: "Excellent: specific, ordered and sufficient to fully answer the question.",
        },
    },
    "writer_helpfulness": {
        "name": "Writer Helpfulness",
        "steps": [
            "Identify exactly what the question in the input asks and note the facts and "
            "county policy given in the input.",
            "Compare every score, status, date and violation stated in the actual output with "
            "the facts and policy in the input. A contradicted or invented fact is a serious "
            "error.",
            "Check whether the actual output directly answers the question and would be "
            "useful to a restaurant owner or diner.",
            "Penalize vague, padded or off-topic text and answers that leave the question "
            "unanswered.",
        ],
        "outcomes": {
            1: "Very poor: wrong or contradicts the facts, or does not answer the question.",
            2: "Poor: partly answers but contains a significant factual error or omission.",
            3: "Acceptable: answers the question with minor inaccuracies, gaps or padding.",
            4: "Good: accurate and useful, with only small omissions or wordiness.",
            5: "Excellent: fully accurate, direct, complete and useful.",
        },
    },
    "final_helpfulness": {
        "name": "Final Answer Helpfulness",
        "steps": [
            "Identify exactly what the question in the input asks.",
            "Check whether the actual output answers that question directly and completely.",
            "Check relevance: the answer must stay on the question and must not contradict "
            "the facts or county policy given in the input.",
            "Check that the answer is clear and that a restaurant owner or diner could act on "
            "it. Penalize irrelevant, vague or contradictory content.",
        ],
        "outcomes": {
            1: "Very poor: irrelevant, wrong, or does not answer the question.",
            2: "Poor: only partly relevant or helpful, with a significant error or omission.",
            3: "Acceptable: relevant and mostly helpful, with minor errors, gaps or padding.",
            4: "Good: relevant, correct and helpful, with only small weaknesses.",
            5: "Excellent: directly relevant, correct, complete and clearly helpful.",
        },
    },
}


def to_1_5(score01):
    """GEval score (0-1, i.e. the 0-10 rubric score / 10) -> 1-5 band."""
    if score01 is None:
        return None
    raw = max(0.0, min(10.0, float(score01) * 10.0))
    for (_lo, hi), label in BANDS:
        if raw <= hi + 0.5:
            return label
    return 5


# ----------------------------------------------------------------------------
# local model for DeepEval
# ----------------------------------------------------------------------------

def _ollama_chat(prompt, schema=None, timeout=None):
    """One bounded call to the local Ollama server. Returns the reply text."""
    base = {"model": cfg.JUDGE_MODEL, "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": cfg.JUDGE_TEMPERATURE, "seed": cfg.JUDGE_SEED}}
    variants = []
    if schema is not None:
        variants.append({"format": schema, "think": False})  # schema-constrained JSON
        variants.append({"format": schema})
        variants.append({"format": "json"})
    else:
        variants.append({"think": False})
        variants.append({})
    last = None
    for extra in variants:
        response = requests.post(cfg.JUDGE_URL, json={**base, **extra},
                                 timeout=timeout or cfg.JUDGE_CALL_TIMEOUT_S)
        if response.status_code == 400:  # option not supported by this Ollama/model
            last = response.text[:200]
            continue
        response.raise_for_status()
        return response.json()["message"]["content"]
    raise RuntimeError(f"Ollama rejected the request: {last}")


def _json_object(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("judge model returned no JSON object")
    return json.loads(text[start:end + 1])


def _deepeval_model():
    from deepeval.models import DeepEvalBaseLLM

    class OllamaJudgeModel(DeepEvalBaseLLM):
        """Local Ollama model behind DeepEval's custom-LLM interface."""

        def __init__(self):
            self.model_name = cfg.JUDGE_MODEL

        def load_model(self):
            return self

        def generate(self, prompt, schema=None):
            if schema is None:
                return _ollama_chat(prompt)
            content = _ollama_chat(prompt, schema=schema.model_json_schema())
            return schema(**_json_object(content))

        async def a_generate(self, prompt, schema=None):
            return self.generate(prompt, schema)

        def get_model_name(self):
            return f"ollama:{cfg.JUDGE_MODEL}"

    return OllamaJudgeModel()


def _build_geval(criterion, model):
    from deepeval.metrics import GEval
    try:
        from deepeval.test_case import SingleTurnParams as Params
    except ImportError:  # older deepeval
        from deepeval.test_case import LLMTestCaseParams as Params
    spec = CRITERIA[criterion]
    kwargs = {"name": spec["name"], "evaluation_steps": list(spec["steps"]),
              "evaluation_params": [Params.INPUT, Params.ACTUAL_OUTPUT], "model": model,
              "async_mode": False, "verbose_mode": False}
    try:
        from deepeval.metrics.g_eval import Rubric
        kwargs["rubric"] = [Rubric(score_range=band, expected_outcome=spec["outcomes"][label])
                            for band, label in BANDS]
    except ImportError:  # no rubric support: put the scale into the steps instead
        kwargs["evaluation_steps"].append(
            "Scoring: " + " ".join(f"{band[0]}-{band[1]} = {spec['outcomes'][label]}"
                                   for band, label in BANDS))
    return GEval(**kwargs)


def _measure(criterion, model, input_text, output_text):
    from deepeval.test_case import LLMTestCase
    metric = _build_geval(criterion, model)
    case = LLMTestCase(input=input_text, actual_output=output_text)
    try:
        metric.measure(case, _show_indicator=False)
    except TypeError:
        metric.measure(case)
    return float(metric.score), (metric.reason or "").strip()


def _mock_measure(criterion, input_text, output_text):
    """Deterministic stand-in (HW10_JUDGE=mock). Never used for reported results."""
    words = len(output_text.split())
    question = set(re.findall(r"[a-z]{4,}", input_text.lower()))
    answer = set(re.findall(r"[a-z]{4,}", output_text.lower()))
    overlap = len(question & answer) / max(1, min(len(question), 25))
    score = max(0.0, min(1.0, 0.2 + 0.6 * min(1.0, overlap) + (0.2 if 30 <= words <= 250 else 0)))
    return round(score, 1), f"mock judge: overlap={overlap:.2f}, words={words}"


class Judge:
    def __init__(self, backend=None):
        self.backend = backend or cfg.JUDGE_BACKEND
        self.failures = 0
        self.unavailable = False
        self.calls = 0
        self._model = None
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=4,
                                                           thread_name_prefix="judge")

    def describe(self):
        info = {"framework": "deepeval GEval", "backend": self.backend,
                "scale": "1-5 (1 very poor, 5 excellent)",
                "band_mapping_0_10_to_1_5": [[list(b), label] for b, label in BANDS],
                "evaluation_params": ["INPUT", "ACTUAL_OUTPUT"], "async_mode": False,
                "call_timeout_s": cfg.JUDGE_CALL_TIMEOUT_S,
                "hard_timeout_s": cfg.JUDGE_HARD_TIMEOUT_S,
                "max_consecutive_failures": cfg.JUDGE_MAX_CONSECUTIVE_FAILURES,
                "criteria": {k: {"name": v["name"], "evaluation_steps": v["steps"],
                                 "rubric": v["outcomes"]} for k, v in CRITERIA.items()}}
        if self.backend == "mock":
            info["model"] = "MOCK heuristic - offline smoke test only, not a real judge"
        else:
            info.update(model=f"ollama:{cfg.JUDGE_MODEL} (local)", url=cfg.JUDGE_URL,
                        temperature=cfg.JUDGE_TEMPERATURE, seed=cfg.JUDGE_SEED, think=False)
            try:
                import deepeval
                info["deepeval_version"] = getattr(deepeval, "__version__", "unknown")
            except ImportError:
                info["deepeval_version"] = "NOT INSTALLED"
        return info

    def health(self):
        """Quick bounded check that the judge can answer at all."""
        if self.backend == "mock":
            return True, "mock judge"
        try:
            import deepeval  # noqa: F401
        except ImportError:
            return False, "deepeval is not installed (pip install deepeval)"
        try:
            reply = _ollama_chat('Reply with the JSON {"ok": true}', schema="json", timeout=90)
            return True, f"{cfg.JUDGE_MODEL} replied: {reply.strip()[:60]}"
        except Exception as exc:  # noqa: BLE001
            return False, f"{type(exc).__name__}: {exc}"

    def score(self, criterion, input_text, output_text):
        """One judgment on the 1-5 scale. Never raises and never blocks past the hard limit."""
        result = {"criterion": criterion, "score": None, "geval_score": None, "reason": "",
                  "status": "ok", "error": None, "ms": 0.0}
        if criterion not in CRITERIA:
            result.update(status="invalid_input", error=f"unknown criterion {criterion}")
            return result
        if not isinstance(input_text, str) or not input_text.strip() \
                or not isinstance(output_text, str) or not output_text.strip():
            result.update(status="invalid_input", error="missing or non-text input/output")
            return result
        if self.unavailable:
            result.update(status="judge_unavailable",
                          error="judge marked unavailable after repeated failures")
            return result
        input_text = input_text[:cfg.JUDGE_MAX_CHARS]
        output_text = output_text[:cfg.JUDGE_MAX_CHARS]
        start = time.perf_counter()
        self.calls += 1
        try:
            if self.backend == "mock":
                geval, reason = _mock_measure(criterion, input_text, output_text)
            else:
                if self._model is None:
                    self._model = _deepeval_model()
                future = self._pool.submit(_measure, criterion, self._model, input_text,
                                           output_text)
                geval, reason = future.result(timeout=cfg.JUDGE_HARD_TIMEOUT_S)
            result.update(score=to_1_5(geval), geval_score=round(geval, 3), reason=reason)
            self.failures = 0
        except concurrent.futures.TimeoutError:
            result.update(status="judge_timeout",
                          error=f"no result within {cfg.JUDGE_HARD_TIMEOUT_S:.0f}s")
            self._failed(result)
        except Exception as exc:  # noqa: BLE001 - bad JSON, connection refused, ...
            result.update(status="judge_error", error=f"{type(exc).__name__}: {exc}"[:300])
            self._failed(result)
        result["ms"] = round((time.perf_counter() - start) * 1000, 1)
        return result

    def _failed(self, result):
        self.failures += 1
        log(COMPONENT, f"{result['criterion']} -> {result['status']}: {result['error']}")
        if self.failures >= cfg.JUDGE_MAX_CONSECUTIVE_FAILURES:
            self.unavailable = True
            log(COMPONENT, f"{self.failures} consecutive failures - judge marked UNAVAILABLE; "
                           "remaining judgments are skipped")

    def close(self):
        self._pool.shutdown(wait=False, cancel_futures=True)
