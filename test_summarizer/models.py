"""Pydantic snapshot models for schema v1 (docs/test-summarizer/SCHEMA.md)."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class _ForbidExtra(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Layer(str, Enum):
    unit = "unit"
    integration = "integration"
    e2e = "e2e"
    unknown = "unknown"


class TestStatus(str, Enum):
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    error = "error"
    unknown = "unknown"


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class RuleId(str, Enum):
    no_oracle = "no_oracle"
    empty_body = "empty_body"
    orphan_report = "orphan_report"
    missing_source = "missing_source"
    skip_or_flake = "skip_or_flake"
    theatrical = "theatrical"
    name_mismatch = "name_mismatch"
    framework_not_product = "framework_not_product"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ShippedKind(str, Enum):
    feat = "feat"
    fix = "fix"
    perf = "perf"
    revert = "revert"
    other = "other"


class TestRecord(_ForbidExtra):
    id: str
    path: str
    name: str
    suite: str = ""
    layer: Layer = Layer.unknown
    oracles: list[str] = Field(default_factory=list)
    doubles: list[str] = Field(default_factory=list)
    status: TestStatus = TestStatus.unknown
    source_present: bool = False
    report_present: bool = False
    needs_llm: list[str] = Field(default_factory=list)


class Finding(_ForbidExtra):
    id: str
    rule_id: RuleId
    severity: Severity
    record_id: str
    evidence: str
    message: str


class Capability(_ForbidExtra):
    id: str
    title: str
    behavior: str
    evidence_record_ids: list[str] = Field(default_factory=list)
    evidence_discounted: bool = False
    confidence: Confidence = Confidence.low


class ShippedItem(_ForbidExtra):
    id: str
    version: str
    kind: ShippedKind
    title: str
    date: str = ""


class Gap(_ForbidExtra):
    shipped_id: str
    capability_id: Optional[str] = None
    reason: str


class Contradiction(_ForbidExtra):
    shipped_id: str
    capability_id: str
    reason: str


class Delta(_ForbidExtra):
    findings_opened: list[str] = Field(default_factory=list)
    findings_closed: list[str] = Field(default_factory=list)
    capabilities_gained: list[str] = Field(default_factory=list)
    capabilities_lost: list[str] = Field(default_factory=list)
    shipped_without_evidence: list[str] = Field(default_factory=list)


class Snapshot(_ForbidExtra):
    schema_version: Literal[1]
    analyzed_repo: str
    git_commit: str = ""
    generated_at: str
    package_path: str = "."
    product_narrative: str = ""
    records: list[TestRecord] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    capabilities: list[Capability] = Field(default_factory=list)
    shipped: list[ShippedItem] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    delta: Optional[Delta] = None
