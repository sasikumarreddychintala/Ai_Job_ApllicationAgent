# Architectural Decision Records (ADRs) (Phase 0)

## ADR 001: Local SQLite over Postgres
- **Context**: The agent requires structured persistence for candidate profile, job listings, match records, resume versions, and application lifecycle tracking.
- **Decision**: Use SQLite 3 stored locally in `data/applications.db`.
- **Rationale**: SQLite requires zero background services or container management, operates completely offline, is single-file portable, and easily handles thousands of job records for a single personal user.

## ADR 002: Ollama Local LLM Inference over Paid APIs
- **Context**: The agent needs LLM capabilities for structured JD parsing, match reasoning, resume tailoring, and open-ended question answering.
- **Decision**: Use Ollama with `llama3.2` or `qwen2.5` locally via HTTP API.
- **Rationale**: Eliminates API costs, guarantees complete candidate data privacy, operates offline, and supports strict native JSON format enforcement via Pydantic JSON schemas.

## ADR 003: Headful Playwright with Human-in-the-Loop CAPTCHA Pause
- **Context**: Modern job portals implement anti-bot protection, Cloudflare checks, and CAPTCHAs.
- **Decision**: Use Playwright in non-headless (`HEADLESS=false`) mode. When a CAPTCHA or unknown interaction is detected, pause execution, save a state checkpoint, emit a local notification, wait for manual human completion, and resume automatically.
- **Rationale**: Programmatic CAPTCHA bypassing is fragile, unreliable, and violates site policies. The Human-in-the-Loop design preserves user control while automating 95% of tedious form filling.

## ADR 004: Strict Immutable Master Resume Policy
- **Context**: LLM resume tailoring can risk hallucinating fake skills, titles, or dates.
- **Decision**: Keep `data/master_resume/` strictly immutable. Tailored resumes are dynamically generated derivative artifacts stored in `data/tailored_resumes/`. Every AI tailored resume must pass validation against candidate profile facts before saving.
- **Rationale**: Preserves candidate integrity, avoids misrepresentation, and allows full auditability of every submitted resume version.
