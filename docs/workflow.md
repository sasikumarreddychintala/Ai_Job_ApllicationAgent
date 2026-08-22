# Application Workflow & State Machine (Phase 0)

## End-to-End Application Lifecycle Workflow

```
[START]
   │
   ▼
[1. Load Candidate Profile] (Immutable master resume + verified candidate JSON)
   │
   ▼
[2. Discover Jobs] (Job source adapters collect job listings)
   │
   ▼
[3. Normalize & Deduplicate] (Stable hash checking against SQLite DB)
   ├─── Already applied / processed? ───► [State: DUPLICATE] ──► (Skip)
   │
   ▼
[4. Analyze JD] (Ollama extracts structured hard requirements & skills)
   │
   ▼
[5. Qualification & Matching Engine]
   ├─── Score < Threshold (e.g., < 70)? ──► [State: SKIPPED] ──► (Skip)
   │
   ▼
[6. Resume Tailoring Engine] (Truthful alignment, generate tailored PDF)
   │
   ▼
[7. Playwright Automation Engine] (Launch headful browser, navigate to application page)
   │
   ├─── CAPTCHA / Bot Barrier Detected? ──► [State: CAPTCHA_WAITING]
   │                                             │
   │                                             ▼
   │                                     [Save Checkpoint & Notify User]
   │                                             │
   │                                             ▼
   │                                     [User Solves CAPTCHA manually]
   │                                             │
   │                                             ▼
   │                                     [Resume Automation from Checkpoint]
   │
   ▼
[8. Form Filling & Answer Generation] (Fill text, dropdowns, upload tailored resume PDF)
   │
   ├─── Unknown Question / Declaration? ──► [State: MANUAL_ACTION_REQUIRED]
   │                                             │
   │                                             ▼
   │                                     [User Fills Field / Approves]
   │
   ▼
[9. Submission Checkpoint]
   ├─── DRY_RUN == True? ────────────────► [State: READY_TO_SUBMIT] ──► (Stop before submit)
   │
   ▼
[10. Submit & Record] ────────────────────► [State: SUBMITTED] ──► (Update SQLite & logs)
   │
   ▼
[Next Job until Daily Limit reached]
```

## State Machine Definitions

| State Name | Classification | Description |
| :--- | :--- | :--- |
| `DISCOVERED` | Initial | Job listing found by adapter and inserted into database. |
| `ANALYZED` | Processing | JD parsed into structured requirements by Ollama. |
| `MATCHED` | Evaluated | Hard rules and scoring calculated. |
| `QUALIFIED` | Decision | Score >= threshold (e.g. >= 70). Ready for resume tailoring. |
| `SKIPPED` | Terminal | Score < threshold or hard constraint violated (e.g. citizenship/visa). |
| `DUPLICATE` | Terminal | Fingerprint hash matches previously processed job. |
| `RESUME_READY` | Prepared | Truthful tailored PDF resume generated and linked. |
| `APPLICATION_STARTED` | Automation | Browser opened and form fields detected. |
| `FORM_FILLED` | Automation | Form fields populated and resume uploaded. |
| `READY_TO_SUBMIT` | Checkpoint | Form completely filled in `DRY_RUN` mode. Awaiting user submission. |
| `SUBMITTED` | Terminal Success | Application submitted successfully and confirmed. |
| `CAPTCHA_WAITING` | Exception State | Automation paused due to CAPTCHA/anti-bot challenge. |
| `MANUAL_ACTION_REQUIRED` | Exception State | Unknown question, file type, or legal declaration encountered. |
| `FAILED` | Terminal Failure | Runtime error, broken selector, or site failure. |
