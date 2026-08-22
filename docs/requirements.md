# Personal AI Job Application Agent — Requirements & Scope (Phase 0)

## 1. Executive Overview
The Personal AI Job Application Agent is a local-first, single-user software system designed to automate job discovery, job description (JD) analysis, candidate resume qualification, truthful resume tailoring, application question answering, dynamic browser form filling, and application tracking.

## 2. Core Scope & Boundaries
- **User Scope**: Single personal user. Multi-tenant infrastructure, SaaS features, authentication/login systems, and payment/subscription gateways are strictly excluded.
- **Execution Model**: Local-first. Execution occurs entirely on the candidate's personal computer.
- **Inference Layer**: Ollama local LLM inference. No paid cloud AI APIs (OpenAI, Anthropic, Google Gemini API) are required for core system execution.
- **Persistence Layer**: Local SQLite database (`data/applications.db`).
- **Browser Engine**: Playwright (Headful mode for visual monitoring & Human-in-the-Loop intervention).

## 3. Automation & Safety Policy
1. **Repetitive Form Automation**: Playwright handles standard, repetitive input fields, dropdowns, file uploads, and radio buttons.
2. **CAPTCHA & Anti-Bot Policy**:
   - The agent **NEVER** attempts to bypass, defeat, solve, or evade CAPTCHAs, Cloudflare checks, or access rate limits programmatically.
   - When a CAPTCHA or human-verification barrier is detected, the agent **immediately pauses**, saves a recovery state checkpoint, issues a local notification, and waits for manual completion by the human user.
3. **Truthfulness Policy**:
   - The agent **NEVER** fabricates skills, dates of employment, job titles, educational degrees, certifications, or projects.
   - The master resume serves as an immutable truth source. Tailoring emphasizes verified, relevant experience and aligns wording with ATS keywords without altering factual truth.
4. **Legal & Compliance Declarations**:
   - The agent **NEVER** auto-submits unknown legal, background check, or authorization declarations without user pre-approval.

## 4. Operational Controls & Thresholds
- **Daily Application Limit**: Configurable limit (default: 10 applications/day) to prevent rate limiting or uncontrolled submission.
- **Qualification Score Threshold**:
   - `< 70`: `SKIP` (Job does not meet qualification criteria)
   - `70 – 79`: `APPLY` (Standard priority)
   - `80 – 89`: `HIGH` (High match priority)
   - `90+`: `VERY_HIGH` (Top tier match priority)
- **Dry-Run Mode**: When `DRY_RUN=true`, the agent populates all form fields and uploads the tailored resume, but stops prior to clicking the final "Submit" button.

## 5. Technology Stack Specifications
| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Core agent orchestration & logic |
| **AI Inference** | Ollama (`llama3.2` / `qwen2.5`) | Local structured JSON generation & semantic evaluation |
| **Browser Engine**| Playwright Python | Web automation & form completion |
| **Database** | SQLite 3 | Application state tracking & audit trail |
| **PDF Parser** | PyMuPDF (`fitz`) | Resume parsing & extraction |
| **DOCX Parser** | `python-docx` | DOCX parsing |
| **Embeddings** | `sentence-transformers` | Local semantic match scoring (optional enhancement) |
