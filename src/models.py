"""
Pydantic models for MCP Legal Assistant data structures.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ============================================================
# ENUMS
# ============================================================


class TaskType(str, Enum):
    """Types of legal tasks."""

    CONTRACT_REVIEW = "contract_review"
    CASE_RESEARCH = "case_research"
    DRAFTING = "drafting"
    DEADLINE = "deadline"
    BILLING = "billing"
    FULL_MATTER = "full_matter"


class RiskLevel(str, Enum):
    """Risk assessment levels."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NEUTRAL = "NEUTRAL"


class UrgencyLevel(str, Enum):
    """Deadline urgency levels."""

    CRITICAL = "CRITICAL"
    IMPORTANT = "IMPORTANT"
    ADMINISTRATIVE = "ADMINISTRATIVE"


class AlertStatus(str, Enum):
    """Alert delivery status."""

    NOT_SENT = "NOT_SENT"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OVERDUE = "OVERDUE"


class VerificationStatus(str, Enum):
    """Citation verification status."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED - needs attorney check"


class DocumentType(str, Enum):
    """Supported document types."""

    NDA = "NDA"
    SAAS_AGREEMENT = "SaaS Agreement"
    EMPLOYMENT = "Employment"
    SERVICE = "Service"
    MSA = "MSA"
    SOW = "SOW"
    OTHER = "Other"


# ============================================================
# BASE MODELS
# ============================================================


class FirmProfile(BaseModel):
    """Law firm profile and configuration."""

    firm_name: str
    jurisdiction: str
    practice_areas: list[str]
    billing_increment: float = 0.1
    conflict_check_required: bool = True
    malpractice_carrier: str | None = None
    attorney_rates: dict[str, float] | None = None


class MatterInfo(BaseModel):
    """Legal matter information."""

    matter_id: str
    client_name: str
    matter_type: str
    jurisdiction: str
    responsible_attorney: str
    opposing_parties: list[str] | None = None
    contract_value: float | None = None
    open_date: date | None = None


class SessionContext(BaseModel):
    """Current session context."""

    session_id: str
    firm_id: str
    matter_id: str | None = None
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# ORCHESTRATOR MODELS
# ============================================================


class OrchestratorInput(BaseModel):
    """Input to the orchestrator agent."""

    task_description: str
    session_context: SessionContext
    matter_info: MatterInfo | None = None
    firm_profile: FirmProfile | None = None
    attachments: list[dict[str, Any]] | None = None


class AttorneyActionItem(BaseModel):
    """Action item requiring attorney attention."""

    item_id: str
    description: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    due_date: datetime | None = None
    related_to: str | None = None


class OrchestratorResult(BaseModel):
    """Result from the orchestrator agent."""

    task_type: TaskType
    matter_id: str
    client_name: str
    jurisdiction: str
    agents_invoked: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    result: dict[str, Any]
    attorney_action_items: list[AttorneyActionItem]
    requires_attorney_review: bool = True
    escalation_flag: bool = False
    escalation_reason: str | None = None
    legal_disclaimer: str
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# CONTRACT REVIEWER MODELS
# ============================================================


class RiskFlag(BaseModel):
    """Individual risk flag in contract review."""

    flag_id: str
    section: str
    clause_number: str | None = None
    risk_level: RiskLevel
    risk_category: str
    issue_description: str
    original_text: str
    suggested_revision: str | None = None
    attorney_action: str


class ContractReviewResult(BaseModel):
    """Result from contract review."""

    review_id: str
    document_name: str
    document_type: str
    parties: dict[str, str]
    effective_date: str | None = None
    governing_law: str | None = None
    contract_value: str | None = None
    overall_risk_level: RiskLevel
    risk_score: int = Field(ge=0, le=100)
    executive_summary: str
    risk_flags: list[RiskFlag]
    missing_clauses: list[str]
    defined_terms_issues: list[str]
    total_high_risks: int = 0
    total_medium_risks: int = 0
    total_low_risks: int = 0
    recommended_negotiation_points: list[str]
    attorney_review_required: bool = True
    legal_disclaimer: str

    @field_validator("total_high_risks", "total_medium_risks", "total_low_risks", mode="before")
    @classmethod
    def count_risks(cls, v, info) -> int:
        if v != 0:
            return v
        # Auto-count from risk_flags if not provided
        risk_flags = info.data.get("risk_flags", [])
        if info.field_name == "total_high_risks":
            return len([f for f in risk_flags if f.risk_level == RiskLevel.HIGH])
        elif info.field_name == "total_medium_risks":
            return len([f for f in risk_flags if f.risk_level == RiskLevel.MEDIUM])
        elif info.field_name == "total_low_risks":
            return len([f for f in risk_flags if f.risk_level == RiskLevel.LOW])
        return v


# ============================================================
# CASE RESEARCHER MODELS
# ============================================================


class CaseFound(BaseModel):
    """Case found during research."""

    citation: str
    court: str
    year: int
    holding: str
    relevant_quote: str | None = None
    pinpoint_citation: str | None = None
    subsequent_history: str | None = None
    relevance_to_matter: str
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    favors_client: bool = True


class ResearchResult(BaseModel):
    """Result from case research."""

    research_id: str
    matter_id: str
    question_presented: str
    jurisdiction: str
    practice_area: str
    brief_answer: str
    research_memo_text: str
    cases_found: list[CaseFound]
    statutes_found: list[str]
    adverse_authority: list[CaseFound] = []
    internal_db_matches: list[dict[str, Any]] = []
    circuit_splits_identified: list[str] = []
    unsettled_law_flags: list[str] = []
    research_confidence: float = Field(ge=0.0, le=1.0)
    attorney_action_items: list[AttorneyActionItem] = []
    legal_disclaimer: str


# ============================================================
# DOCUMENT DRAFTER MODELS
# ============================================================


class AttorneyNote(BaseModel):
    """Note for attorney review."""

    section: str
    note: str
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"


class DraftResult(BaseModel):
    """Result from document drafting."""

    draft_id: str
    matter_id: str
    document_type: str
    document_title: str
    jurisdiction: str
    parties: dict[str, Any]
    effective_date: str | None = None
    draft_version: str = "v0.1 - First Draft for Attorney Review"
    full_document_text: str
    docx_file_path: str | None = None
    attorney_notes: list[AttorneyNote] = []
    unfilled_placeholders: list[str] = []
    jurisdiction_flags: list[str] = []
    consistency_issues: list[str] = []
    clause_library_suggestions: list[str] = []
    word_count: int = 0
    estimated_review_time_minutes: int = 0
    attorney_review_required: bool = True
    legal_disclaimer: str


# ============================================================
# DEADLINE TRACKER MODELS
# ============================================================


class DeadlineInfo(BaseModel):
    """Individual deadline information."""

    deadline_id: str
    description: str
    due_date: date
    days_remaining: int
    urgency: UrgencyLevel
    category: str
    court_rule_reference: str | None = None
    calculation_method: str
    alert_status: AlertStatus = AlertStatus.NOT_SENT
    requires_attorney_confirmation: bool = True


class MatterDeadlines(BaseModel):
    """Deadlines for a single matter."""

    matter_id: str
    client_name: str
    matter_type: str
    responsible_attorney: str
    deadlines: list[DeadlineInfo]


class DeadlineReport(BaseModel):
    """Daily deadline report."""

    docket_report_date: date
    firm_id: str
    deadlines_today: list[DeadlineInfo] = []
    deadlines_this_week: list[DeadlineInfo] = []
    deadlines_next_30_days: list[DeadlineInfo] = []
    sol_expiring_90_days: list[DeadlineInfo] = []
    overdue_deadlines: list[DeadlineInfo] = []
    alerts_sent: list[dict[str, Any]] = []
    matters: list[MatterDeadlines] = []
    system_health: dict[str, int] = {}


# ============================================================
# BILLING CALCULATOR MODELS
# ============================================================


class TimeEntry(BaseModel):
    """Individual time entry."""

    entry_id: str
    date: date
    timekeeper_id: str
    timekeeper_name: str
    matter_id: str
    hours: float = Field(ge=0.0)
    description: str
    billing_code: str | None = None
    billable: bool = True
    rate: float | None = None


class ExpenseEntry(BaseModel):
    """Expense entry for billing."""

    expense_id: str
    date: date
    description: str
    amount: float
    matter_id: str


class TrustAccount(BaseModel):
    """Trust account information."""

    balance_before: float
    applied_to_invoice: float
    balance_after: float
    replenishment_requested: bool = False


class MatterBudget(BaseModel):
    """Matter budget tracking."""

    total_budget: float | None = None
    total_billed_to_date: float = 0.0
    percent_consumed: float = 0.0
    projected_at_completion: float | None = None
    over_budget_flag: bool = False


class BillingResult(BaseModel):
    """Result from billing calculation."""

    billing_id: str
    matter_id: str
    client_name: str
    billing_period: dict[str, date]
    invoice_number: str
    time_entries_processed: int = 0
    time_entries_flagged: list[dict[str, Any]] = []
    block_billing_detected: list[dict[str, Any]] = []
    total_hours: float = 0.0
    total_fees: str = "$0.00"
    total_expenses: str = "$0.00"
    total_invoice_amount: str = "$0.00"
    invoice_html: str | None = None
    invoice_pdf_path: str | None = None
    trust_account: TrustAccount | None = None
    ethics_flags: list[str] = []
    matter_budget: MatterBudget | None = None
    ready_to_send: bool = False
    requires_attorney_approval: bool = True


# ============================================================
# MCP TOOL SCHEMAS
# ============================================================


class ContractReviewerInput(BaseModel):
    """Input for contract review tool."""

    document_text: str
    document_name: str
    matter_info: MatterInfo
    firm_profile: FirmProfile | None = None


class CaseResearcherInput(BaseModel):
    """Input for case research tool."""

    legal_question: str
    jurisdiction: str
    practice_area: str
    matter_info: MatterInfo
    favorable_research: bool = True


class DocumentDrafterInput(BaseModel):
    """Input for document drafting tool."""

    document_type: str
    party_details: dict[str, Any]
    key_terms: dict[str, Any]
    jurisdiction: str
    special_instructions: str | None = None
    matter_info: MatterInfo


class DeadlineTrackerInput(BaseModel):
    """Input for deadline tracking tool."""

    firm_id: str
    matter_ids: list[str] | None = None
    generate_report: bool = True


class BillingCalculatorInput(BaseModel):
    """Input for billing calculation tool."""

    matter_id: str
    # The billing agent read input_data.client_name, which was never a field:
    # every request raised AttributeError and the API returned 500.
    client_name: str | None = None
    billing_period_start: date
    billing_period_end: date
    include_expenses: bool = True
    generate_invoice: bool = True
