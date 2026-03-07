"""
Contract Reviewer Agent - Precision contract analysis for risk detection.
"""
import logging
import uuid
import json
from typing import Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.models import (
    ContractReviewerInput,
    ContractReviewResult,
    RiskFlag,
    RiskLevel,
    MatterInfo,
    FirmProfile,
)
from src.pdf_parser import parse_text_content
from src.config import get_settings

logger = logging.getLogger(__name__)


class ContractReviewerAgent:
    """
    AI agent for contract review and risk analysis.
    Identifies risk clauses, missing protections, and unfavorable terms.
    """
    
    LEGAL_DISCLAIMER = (
        "This contract review is AI-assisted analysis only. It does not constitute "
        "legal advice. All findings must be reviewed and validated by a licensed "
        "attorney before any action is taken."
    )
    
    def __init__(self, model: Optional[str] = None):
        """
        Initialize Contract Reviewer agent.
        
        Args:
            model: Model to use (defaults to Claude 3.5 Sonnet)
        """
        settings = get_settings()
        self.model_name = model or settings.contract_reviewer_model
        
        # Use Claude for best document analysis
        if "claude" in self.model_name.lower():
            self.llm = ChatAnthropic(
                model=self.model_name,
                api_key=settings.anthropic_api_key,
                temperature=0.1,
                max_tokens=8192,
            )
        else:
            self.llm = ChatOpenAI(
                model=self.model_name,
                api_key=settings.openai_api_key,
                temperature=0.1,
                max_tokens=8192,
            )
        
        self.prompt = self._build_prompt()
    
    def _build_prompt(self) -> ChatPromptTemplate:
        """Build the contract review prompt."""
        system_prompt = """
You are ContractReviewer — a precision contract analysis engine.
Review the contract and identify risk clauses, missing protections, and unfavorable terms.

CRITICAL: You identify and flag — you do NOT advise.
You never tell a client what to do. You surface issues for the reviewing attorney.

Analyze the contract on these dimensions:

RISK LEVELS:
- HIGH: Requires immediate attorney review before signing
- MEDIUM: Requires attorney clarification or negotiation  
- LOW: Standard clause, acceptable with modifications
- NEUTRAL: Informational only

RISK CATEGORIES TO ANALYZE:
1. PAYMENT & FINANCIAL - Look for unlimited obligations, auto-renewal traps, hidden fees
2. INTELLECTUAL PROPERTY - Watch for overbroad IP assignment, vague ownership
3. LIABILITY & INDEMNIFICATION - Flag unlimited indemnity, one-sided terms
4. CONFIDENTIALITY - Identify overly broad definitions, missing carve-outs
5. TERMINATION - Note one-sided termination, insufficient notice periods
6. GOVERNING LAW & DISPUTE - Flag unfavorable jurisdictions, mandatory arbitration
7. NON-COMPETE - Identify overbroad scope, duration > 2 years

MISSING CLAUSE DETECTION:
Check for: Force Majeure, Liability Cap, Mutual Indemnification, Dispute Resolution,
Governing Law, Assignment Restrictions, Amendment Procedure, Merger Clause, Severability

OUTPUT REQUIREMENTS:
Return a JSON object with this exact structure:
{{
  "review_id": "unique-id",
  "document_name": "document name",
  "document_type": "NDA|SaaS Agreement|Employment|Service|Other",
  "parties": {{"party_a": "name", "party_b": "name"}},
  "effective_date": "date or null",
  "governing_law": "jurisdiction or null",
  "contract_value": "value or null",
  "overall_risk_level": "HIGH|MEDIUM|LOW",
  "risk_score": 0-100,
  "executive_summary": "2-3 sentence summary",
  "risk_flags": [
    {{
      "flag_id": "id",
      "section": "section name",
      "clause_number": "number or null",
      "risk_level": "HIGH|MEDIUM|LOW",
      "risk_category": "category",
      "issue_description": "description",
      "original_text": "exact text",
      "suggested_revision": "revision or null",
      "attorney_action": "required action"
    }}
  ],
  "missing_clauses": ["list of missing clauses"],
  "defined_terms_issues": ["list of issues"],
  "total_high_risks": 0,
  "total_medium_risks": 0,
  "total_low_risks": 0,
  "recommended_negotiation_points": ["points"],
  "attorney_review_required": true,
  "legal_disclaimer": "{disclaimer}"
}}

Contract to review:
{contract_text}

Jurisdiction: {jurisdiction}
Client: {client_name}
"""
        
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
        ])
    
    async def review(self, input_data: ContractReviewerInput) -> ContractReviewResult:
        """
        Review a contract and return risk analysis.
        
        Args:
            input_data: Contract review input
            
        Returns:
            ContractReviewResult with analysis
        """
        try:
            logger.info(f"Starting contract review: {input_data.document_name}")
            
            # Parse the document
            parsed = parse_text_content(
                input_data.document_text,
                input_data.document_name
            )
            
            # Build the chain
            chain = self.prompt | self.llm | JsonOutputParser()
            
            # Execute review
            response = await chain.ainvoke({
                "contract_text": input_data.document_text[:50000],  # Truncate if too long
                "jurisdiction": input_data.matter_info.jurisdiction,
                "client_name": input_data.matter_info.client_name,
                "disclaimer": self.LEGAL_DISCLAIMER,
            })
            
            # Parse and validate response
            result = self._parse_result(response, input_data)
            
            logger.info(
                f"Contract review complete: {result.total_high_risks} high, "
                f"{result.total_medium_risks} medium, {result.total_low_risks} low risks"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Contract review failed: {e}")
            raise
    
    def _parse_result(
        self,
        response: dict,
        input_data: ContractReviewerInput,
    ) -> ContractReviewResult:
        """Parse and validate the LLM response."""
        # Count risks
        risk_flags = []
        for flag in response.get("risk_flags", []):
            risk_flags.append(RiskFlag(
                flag_id=flag.get("flag_id", str(uuid.uuid4())[:8]),
                section=flag.get("section", "Unknown"),
                clause_number=flag.get("clause_number"),
                risk_level=RiskLevel(flag.get("risk_level", "MEDIUM")),
                risk_category=flag.get("risk_category", "General"),
                issue_description=flag.get("issue_description", ""),
                original_text=flag.get("original_text", ""),
                suggested_revision=flag.get("suggested_revision"),
                attorney_action=flag.get("attorney_action", ""),
            ))
        
        # Auto-count if not provided
        total_high = response.get("total_high_risks", 0) or len([
            f for f in risk_flags if f.risk_level == RiskLevel.HIGH
        ])
        total_medium = response.get("total_medium_risks", 0) or len([
            f for f in risk_flags if f.risk_level == RiskLevel.MEDIUM
        ])
        total_low = response.get("total_low_risks", 0) or len([
            f for f in risk_flags if f.risk_level == RiskLevel.LOW
        ])
        
        # Determine overall risk level
        if total_high > 0:
            overall_risk = RiskLevel.HIGH
        elif total_medium > 2:
            overall_risk = RiskLevel.MEDIUM
        else:
            overall_risk = RiskLevel.LOW
        
        # Calculate risk score (0-100)
        risk_score = min(100, (total_high * 20) + (total_medium * 10) + (total_low * 3))
        
        return ContractReviewResult(
            review_id=response.get("review_id", str(uuid.uuid4())[:8]),
            document_name=input_data.document_name,
            document_type=response.get("document_type", "Other"),
            parties=response.get("parties", {}),
            effective_date=response.get("effective_date"),
            governing_law=response.get("governing_law"),
            contract_value=response.get("contract_value"),
            overall_risk_level=overall_risk,
            risk_score=risk_score,
            executive_summary=response.get("executive_summary", ""),
            risk_flags=risk_flags,
            missing_clauses=response.get("missing_clauses", []),
            defined_terms_issues=response.get("defined_terms_issues", []),
            total_high_risks=total_high,
            total_medium_risks=total_medium,
            total_low_risks=total_low,
            recommended_negotiation_points=response.get("recommended_negotiation_points", []),
            attorney_review_required=True,
            legal_disclaimer=self.LEGAL_DISCLAIMER,
        )
    
    def review_sync(self, input_data: ContractReviewerInput) -> ContractReviewResult:
        """
        Synchronous version of contract review.
        
        Args:
            input_data: Contract review input
            
        Returns:
            ContractReviewResult with analysis
        """
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.review(input_data))
