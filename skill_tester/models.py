from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillInfo:
    name: str
    description: str
    path: Path
    body: str = ""
    when_to_use: str = ""
    trigger_phrases: list[str] = field(default_factory=list)


@dataclass
class TestCase:
    query: str
    expect_trigger: bool
    category: str = "positive"  # positive, negative, edge


@dataclass
class TestResult:
    case: TestCase
    triggered: bool
    duration_ms: int = 0
    cost_usd: float = 0.0
    raw_output: list[dict] = field(default_factory=list)
    error: str | None = None
    rival_skill: str | None = None
    diagnosis: str | None = None

    @property
    def passed(self) -> bool:
        return self.case.expect_trigger == self.triggered


@dataclass
class ScoreCard:
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def verdict(self) -> str:
        if self.f1 >= 0.90:
            return "OPTIMAL"
        if self.f1 >= 0.75:
            return "GOOD"
        return "NEEDS_WORK"


@dataclass
class HealthCheck:
    level: str  # "ERROR", "WARN", "INFO"
    code: str  # "E1", "W1", etc.
    message: str
    field: str  # "when_to_use", "description", etc.


@dataclass
class FrontmatterHealth:
    skill_name: str
    context_cost: int
    budget_pct: float
    has_when_to_use: bool
    has_hyphenated_when_to_use: bool
    redundancy_score: float
    checks: list[HealthCheck] = field(default_factory=list)

    @property
    def grade(self) -> str:
        if any(c.level == "ERROR" for c in self.checks):
            return "BROKEN"
        if any(c.level == "WARN" for c in self.checks):
            return "IMPROVABLE"
        return "HEALTHY"


@dataclass
class OptimizationRound:
    round_num: int
    description: str
    when_to_use: str
    score: ScoreCard
    false_negatives: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)
    num_regression_cases: int = 0
    name_suggestion: str | None = None


@dataclass
class OptimizationResult:
    skill_name: str
    skill_path: Path
    original_description: str
    original_when_to_use: str
    final_description: str
    final_when_to_use: str
    rounds: list[OptimizationRound] = field(default_factory=list)
    converged: bool = False
    target_f1: float = 0.90
