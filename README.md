# MCP Legal Assistant Agent

> AI-powered legal research and drafting assistant for law firms  
> **Stack:** LangGraph + CrewAI + LangChain + Pinecone + MCP + FastAPI  
> **Author:** Ismail Sajid — Agentic AI Engineer

---

## ⚖️ CRITICAL LEGAL DISCLAIMER

**This system is a legal RESEARCH and DRAFTING ASSISTANT only.**

- It does **NOT** provide legal advice
- Every output **MUST** be reviewed and approved by a licensed attorney before use
- Always inject the legal disclaimer into every agent output

---

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [MCP Tools](#mcp-tools)
- [Testing](#testing)
- [Security & Compliance](#security--compliance)
- [Contributing](#contributing)

---

## ✨ Features

### Specialist AI Agents

| Agent | Function | Model |
|-------|----------|-------|
| **ContractReviewer** | Risk clause detection, redline analysis | Claude 3.5 Sonnet |
| **CaseResearcher** | Precedent search, statute lookup | GPT-4o |
| **DocumentDrafter** | Template generation, clause drafting | Claude 3.5 Sonnet |
| **DeadlineTracker** | Court dates, filing deadlines, alerts | GPT-4o |
| **BillingCalculator** | Time tracking, invoice generation | GPT-4o |

### Key Capabilities

- 📄 **Contract Analysis** — Identify risk clauses, missing protections, unfavorable terms
- ⚖️ **Legal Research** — Case law, statutes, regulations with verified citations
- 📝 **Document Drafting** — First-draft contracts, pleadings, letters
- 📅 **Deadline Management** — Court dates, filing deadlines, statute of limitations
- 💰 **Billing Operations** — Time entries, fee calculation, invoice generation
- 🔍 **Vector Search** — Pinecone-powered semantic search across firm knowledge base

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Server                           │
│                    (REST API Endpoints)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LangGraph Orchestrator                     │
│                  (Task Classification & Routing)                │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌───────────────┐
│   Contract    │   │     Case        │   │   Document    │
│   Reviewer    │   │   Researcher    │   │   Drafter     │
└───────────────┘   └─────────────────┘   └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌───────────────┐
│   Deadline    │   │    Billing      │   │   Pinecone    │
│   Tracker     │   │   Calculator    │   │  Vector Store │
└───────────────┘   └─────────────────┘   └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Integrations                        │
│   CourtListener API │ Google Calendar │ Stripe │ Twilio        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Pinecone account (for vector search)
- OpenAI API key
- Anthropic API key (recommended for Claude)

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd "MCP LEGAL ASSISTANT AGENT"

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac

# Edit .env with your API keys
# Then start the server
python -m src.server.server
```

### Install as Package

```bash
pip install -e .

# Run MCP server
legal-assistant-mcp

# Run FastAPI server
legal-assistant-server
```

---

## ⚙️ Configuration

### Environment Variables (.env)

```ini
# LLM API Keys
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Pinecone Vector Database
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-west-2
PINECONE_INDEX_NAME=legal-assistant-index

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/legal_assistant

# Google Calendar API (Deadline Tracker)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Twilio (SMS Alerts)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token

# Stripe (Billing)
STRIPE_SECRET_KEY=sk_live_your-stripe-secret-key

# Court Listener API (Case Research)
COURTLISTENER_API_KEY=your-courtlistener-api-key

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
```

---

## 💻 Usage

### Python SDK

```python
from src.orchestrator import LegalOrchestrator
from src.models import OrchestratorInput, SessionContext, MatterInfo

# Initialize orchestrator
orchestrator = LegalOrchestrator()

# Create input
input_data = OrchestratorInput(
    task_description="Review this contract for risk clauses",
    session_context=SessionContext(
        session_id="session-123",
        firm_id="firm-456",
        matter_id="matter-789",
        user_id="user-001",
    ),
    matter_info=MatterInfo(
        matter_id="matter-789",
        client_name="Acme Corp",
        matter_type="Contract Review",
        jurisdiction="Texas",
        responsible_attorney="John Doe",
    ),
    attachments=[{
        "document_text": "...contract text...",
        "document_name": "Service Agreement.pdf",
    }],
)

# Process task
result = await orchestrator.process(input_data)

# Access results
print(f"Task Type: {result.task_type}")
print(f"Agents Invoked: {result.agents_invoked}")
print(f"Confidence: {result.confidence}")
print(f"Risk Flags: {len(result.result.get('contract_review', {}).get('risk_flags', []))}")
```

### Individual Agent Usage

```python
from src.agents import ContractReviewerAgent
from src.models import ContractReviewerInput, MatterInfo

# Initialize agent
agent = ContractReviewerAgent()

# Create input
input_data = ContractReviewerInput(
    document_text=contract_text,
    document_name="NDA Agreement",
    matter_info=MatterInfo(
        matter_id="MATTER-001",
        client_name="Client Name",
        matter_type="Contract Review",
        jurisdiction="Texas",
        responsible_attorney="Attorney Name",
    ),
)

# Review contract
result = await agent.review(input_data)
print(f"Risk Score: {result.risk_score}")
print(f"High Risks: {result.total_high_risks}")
```

### REST API Usage

```bash
# Contract Review
curl -X POST http://localhost:8000/api/v1/contract/review \
  -H "Content-Type: application/json" \
  -d '{
    "document_text": "...",
    "document_name": "Agreement.pdf",
    "matter_id": "MATTER-001",
    "client_name": "Client Name",
    "jurisdiction": "Texas"
  }'

# Case Research
curl -X POST http://localhost:8000/api/v1/case/research \
  -H "Content-Type: application/json" \
  -d '{
    "legal_question": "What is the statute of limitations for breach of contract in Texas?",
    "jurisdiction": "Texas",
    "practice_area": "Contract",
    "matter_id": "MATTER-001",
    "client_name": "Client Name"
  }'

# Document Drafting
curl -X POST http://localhost:8000/api/v1/document/draft \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "NDA",
    "party_details": {"disclosing_party": "Company A", "receiving_party": "Company B"},
    "key_terms": {"confidentiality_period": "2 years"},
    "jurisdiction": "Texas",
    "matter_id": "MATTER-001",
    "client_name": "Client Name"
  }'
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API information |
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/contract/review` | Review contract for risks |
| `POST` | `/api/v1/case/research` | Conduct legal research |
| `POST` | `/api/v1/document/draft` | Draft legal document |
| `POST` | `/api/v1/deadlines/check` | Check deadlines |
| `POST` | `/api/v1/billing/calculate` | Calculate billing |
| `POST` | `/api/v1/orchestrate` | Auto-route to specialist |
| `GET` | `/api/v1/templates` | List document templates |
| `POST` | `/api/v1/validate/time-description` | Validate time entry |

---

## 🔧 MCP Tools

The system exposes these MCP tools for integration:

- `contract_reviewer` — Contract risk analysis
- `case_researcher` — Legal case research
- `document_drafter` — Document generation
- `deadline_tracker` — Deadline management
- `billing_calculator` — Billing operations

### MCP Client Example

```python
from mcp import ClientSession

async with ClientSession() as session:
    # List available tools
    tools = await session.list_tools()
    
    # Call contract reviewer
    result = await session.call_tool(
        "contract_reviewer",
        {
            "document_text": "...",
            "document_name": "Agreement.pdf",
            "matter_id": "MATTER-001",
            "client_name": "Client",
            "jurisdiction": "Texas",
        }
    )
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_contract_reviewer.py -v

# Run async tests
pytest tests/ -v --asyncio-mode=auto
```

---

## 🔒 Security & Compliance

### Data Protection

- **Encryption:** AES-256 at rest, TLS 1.3 in transit
- **Access Control:** Role-based access (attorney/paralegal/admin)
- **Privilege:** Attorney-client privilege maintained
- **Audit Logs:** All actions logged with timestamps

### Compliance

- **HIPAA:** Compliant for health-related matters
- **GDPR:** Compliant for EU party data
- **SOX:** Compliant for public company matters
- **IOLA:** Trust account handling compliant

### Human Escalation Triggers

The system automatically escalates to human attorney when:

- Contract value exceeds $500,000
- Criminal matter detected
- Constitutional/civil rights issues
- Cross-border/international jurisdiction
- Conflict of interest flagged
- Statute of limitations within 30 days
- Client asks for legal advice (not research)
- Output confidence below 0.75

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/
```

---

## 📄 License

MIT License — See LICENSE file for details

---

## 📞 Support

For support and questions:

- **Documentation:** `/docs` endpoint when server is running
- **Issues:** GitHub Issues
- **Email:** agentic.ai.engineer@example.com

---

## 🙏 Acknowledgments

- LangChain team for the excellent framework
- Anthropic for Claude models
- OpenAI for GPT models
- Pinecone for vector search
- CourtListener for legal data API

---

**Built with ❤️ for the legal community**

*Remember: This is a research and drafting assistant only. All output must be reviewed by a licensed attorney.*
