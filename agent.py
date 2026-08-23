import sys
import argparse
import urllib.request
import json
from pathlib import Path

from config import settings
from src.utils.logger import logger
from src.database.models import init_db

def check_python_environment() -> bool:
    """Verifies Python version and key library imports."""
    logger.info("[bold cyan]1/4 Checking Python environment...[/bold cyan]")
    py_ver = sys.version_info
    if py_ver < (3, 10):
        logger.error(f"Python 3.10+ required. Current version: {sys.version}")
        return False
    
    missing_libs = []
    libs = [
        ("ollama", "ollama"),
        ("playwright", "playwright"),
        ("pymupdf (fitz)", "fitz"),
        ("python-docx", "docx"),
        ("pydantic", "pydantic"),
        ("rich", "rich"),
    ]
    for name, module in libs:
        try:
            __import__(module)
        except ImportError:
            missing_libs.append(name)
            
    if missing_libs:
        logger.error(f"Missing libraries: {', '.join(missing_libs)}. Please run: pip install -r requirements.txt")
        return False
        
    logger.info(f" Python {py_ver.major}.{py_ver.minor}.{py_ver.micro} & dependencies verified.")
    return True

def check_sqlite_database() -> bool:
    """Verifies SQLite database initialization."""
    logger.info("[bold cyan]2/4 Checking SQLite database...[/bold cyan]")
    try:
        conn = init_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        required_tables = [
            "candidate_profile", "jobs", "job_matches", "resume_versions",
            "applications", "application_answers", "application_events", "agent_runs", "settings"
        ]
        missing_tables = [t for t in required_tables if t not in tables]
        if missing_tables:
            logger.error(f"Database missing required tables: {missing_tables}")
            return False
        conn.close()
        logger.info(f" SQLite database verified with {len(tables)} tables.")
        return True
    except Exception as e:
        logger.error(f"SQLite DB check failed: {e}")
        return False

def check_ollama_service() -> bool:
    """Verifies reachability of local Ollama service and target model."""
    logger.info("[bold cyan]3/4 Checking Ollama AI service...[/bold cyan]")
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                logger.info(f" Ollama server online at {settings.OLLAMA_BASE_URL}.")
                
                # Check if configured model is pulled
                target = settings.OLLAMA_MODEL
                matched = any(target in m for m in models)
                if matched:
                    logger.info(f" Configured Ollama model '{target}' is installed and ready.")
                else:
                    logger.warning(
                        f" Model '{target}' not found in installed models: {models}. "
                        f"Please run: ollama pull {target}"
                    )
                return True
    except Exception as e:
        logger.warning(
            f" Ollama service unreachable at {settings.OLLAMA_BASE_URL} ({e}). "
            "Please ensure Ollama is installed and running (`ollama serve`)."
        )
        return False

def check_playwright_browser() -> bool:
    """Verifies Playwright browser installation."""
    logger.info("[bold cyan]4/4 Checking Playwright browser engine...[/bold cyan]")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content("<html><body><h1>Health Check</h1></body></html>")
            title = page.title()
            browser.close()
            logger.info(" Playwright Chromium browser verified successfully.")
            return True
    except Exception as e:
        logger.error(
            f"Playwright browser launch failed: {e}. "
            "Please run: playwright install chromium"
        )
        return False

def run_health_check() -> bool:
    """Runs system startup/health check for Python, SQLite, Ollama, and Playwright."""
    logger.info("=" * 60)
    logger.info("[bold gold1]PERSONAL AI JOB APPLICATION AGENT — STARTUP HEALTH CHECK[/bold gold1]")
    logger.info("=" * 60)
    
    results = [
        ("Python Environment", check_python_environment()),
        ("SQLite Database", check_sqlite_database()),
        ("Ollama AI Service", check_ollama_service()),
        ("Playwright Browser", check_playwright_browser()),
    ]
    
    logger.info("=" * 60)
    logger.info("[bold white]SUMMARY RESULTS:[/bold white]")
    all_passed = True
    for name, status in results:
        status_str = "[green]PASS[/green]" if status else "[red]FAIL / WARNING[/red]"
        logger.info(f" - {name:22s}: {status_str}")
        if not status and name in ["Python Environment", "SQLite Database"]:
            all_passed = False

    if all_passed:
        logger.info("[bold green] System health check complete. Core foundation is operational![/bold green]")
    else:
        logger.warning("[bold yellow] Startup check complete with warnings/failures. Please review above logs.[/bold yellow]")
    return all_passed

def display_candidate_profile():
    """Prints formatted candidate profile using Rich formatting."""
    from src.resume.profile import ProfileManager
    from rich.table import Table
    from rich.panel import Panel
    
    pm = ProfileManager()
    profile = pm.load_profile()
    if not profile:
        logger.warning("[yellow]No candidate profile found. Please import a resume using: python agent.py --import-resume <path>[/yellow]")
        return
        
    c = profile.contact_info
    logger.info("=" * 60)
    logger.info(f"[bold gold1]VERIFIED CANDIDATE PROFILE: {c.full_name}[/bold gold1]")
    logger.info(f"Email: {c.email} | Phone: {c.phone or 'N/A'} | Location: {c.location or 'N/A'}")
    if c.linkedin:
        logger.info(f"LinkedIn: {c.linkedin}")
    if c.github:
        logger.info(f"GitHub: {c.github}")
    logger.info("=" * 60)
    
    if profile.summary:
        logger.info(f"[bold cyan]Summary:[/bold cyan]\n{profile.summary}")
        
    if profile.skills:
        logger.info(f"[bold cyan]Skills:[/bold cyan] {', '.join(profile.skills)}")
        
    if profile.experience:
        logger.info("\nWork Experience:")
        for exp in profile.experience:
            period = f"{exp.start_date} - {exp.end_date or 'Present'}"
            logger.info(f"  * [bold]{exp.position}[/bold] at [bold]{exp.company}[/bold] ({period})")
            for h in exp.highlights[:2]:
                logger.info(f"    - {h}")

    if profile.education:
        logger.info("\nEducation:")
        for edu in profile.education:
            logger.info(f"  * [bold]{edu.degree}[/bold] from [bold]{edu.institution}[/bold]")

    if profile.custom_answers:
        logger.info("\n[bold cyan]Pre-approved Custom Answers:[/bold cyan]")
        for k, v in profile.custom_answers.items():
            logger.info(f"  - [bold]{k}[/bold]: {v}")

def main():
    parser = argparse.ArgumentParser(description="Personal AI Job Application Agent CLI")
    parser.add_argument("--check", action="store_true", help="Run environment and system health check")
    parser.add_argument("--import-resume", type=str, help="Path to master resume PDF or DOCX file to import")
    parser.add_argument("--show-profile", action="store_true", help="Display verified candidate profile summary")
    parser.add_argument("--edit-answer", nargs=2, metavar=("QUESTION_KEY", "ANSWER_VALUE"), help="Set/Update pre-approved application answer")
    parser.add_argument("--discover-jobs", action="store_true", help="Run job discovery across source adapters")
    parser.add_argument("--search", type=str, default="", help="Keyword search filter for job discovery (e.g. 'Python')")
    parser.add_argument("--location", type=str, default="", help="Location filter for job discovery (e.g. 'Remote')")
    parser.add_argument("--time-range", choices=["24h", "3d", "7d"], default="3d", help="Recency filter: '24h' (past 24 hours), '3d' (past 3 days), or '7d'")
    parser.add_argument("--analyze-jobs", action="store_true", help="Run JD Analysis on pending DISCOVERED jobs")
    parser.add_argument("--match-jobs", action="store_true", help="Run Resume <-> JD Matching on pending ANALYZED jobs")
    parser.add_argument("--tailor-resumes", action="store_true", help="Generate tailored PDF resumes for pending QUALIFIED jobs")
    parser.add_argument("--answer-question", type=str, help="Formulate truthful answer for an application question")
    parser.add_argument("--approve-answer", nargs=2, metavar=("QUESTION", "ANSWER"), help="Save user-approved reusable answer")
    parser.add_argument("--run-agent", action="store_true", help="Run full end-to-end local AI job application agent pipeline")
    parser.add_argument("--show-history", action="store_true", help="Display application tracking history table")
    parser.add_argument("--show-events", type=int, metavar="JOB_ID", help="Display lifecycle event timeline for a job")
    parser.add_argument("--export-audit", choices=["json", "csv"], help="Export audit logs to JSON or CSV file")
    parser.add_argument("--send-test-notification", action="store_true", help="Send a test alert across all notification channels")
    parser.add_argument("--apply-url", type=str, metavar="URL", help="Execute targeted pilot run on a specific job URL")
    parser.add_argument("--live", action="store_true", help="Perform live submission (clicks Submit button) when used with --apply-url")
    parser.add_argument("--login", action="store_true", help="Open persistent browser window to log in to LinkedIn/Naukri/Indeed and save session cookies forever")
    parser.add_argument("--ui", action="store_true", help="Launch the local web dashboard interface")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the local dashboard server to (default: 8000)")
    parser.add_argument("--schedule", nargs="?", const="08:00", help="Run automated background morning job discovery at specified time (default: 08:00)")
    parser.add_argument("--telegram-bot", action="store_true", help="Launch standalone 2-Way Interactive Telegram Bot assistant")
    parser.add_argument("--search-rag", type=str, metavar="QUERY", help="Perform semantic RAG retrieval on candidate knowledge base")
    parser.add_argument("--auto-apply", action="store_true", help="One-command full workflow: upload resume, discover matching jobs, and apply")
    parser.add_argument("--resume", type=str, help="Path to resume file (used with --auto-apply)")
    args = parser.parse_args()

    if args.login:
        logger.info("[bold cyan] Starting Interactive Persistent Login Setup Mode...[/bold cyan]")
        logger.info("Opening browser window so you can log into LinkedIn, Naukri, Indeed, and Google.")
        from src.automation.browser import BrowserManager
        with BrowserManager(headless=False) as page:
            try:
                page.goto("https://www.linkedin.com/login")
            except Exception:
                pass
            logger.info("[bold green] Browser is open! Log into all your accounts now. When finished, simply close the browser window or press Enter in this terminal.[/bold green]")
            try:
                input()
            except Exception:
                import time
                while not page.is_closed():
                    time.sleep(1)
        logger.info("[bold green] Session cookies and login credentials saved permanently in 'data/logs/browser_context/'![/bold green]")
        return

    if args.telegram_bot:
        from src.notifications.telegram_bot import telegram_bot
        if not telegram_bot.is_configured:
            logger.error("[bold red]Telegram Bot Token or Chat ID not configured in .env[/bold red]")
            return
        telegram_bot.start()
        logger.info("[bold green] 2-Way Interactive Telegram Assistant is online and listening! Press Ctrl+C to stop.[/bold green]")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            telegram_bot.stop()
            logger.info("[bold yellow]Telegram Bot stopped by user.[/bold yellow]")
        return

    if args.schedule:
        from src.automation.scheduler import scheduler
        scheduler.schedule_time = args.schedule
        scheduler.start()
        logger.info(f"[bold green] Morning Auto-Pilot active! Target daily run: {args.schedule}. Press Ctrl+C to stop.[/bold green]")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
            logger.info("[bold yellow]Scheduler stopped by user.[/bold yellow]")
        return

    if args.auto_apply:
        if args.resume:
            from src.resume.profile import ProfileManager
            from src.resume.parser import parse_resume_to_candidate_profile
            profile = parse_resume_to_candidate_profile(args.resume)
            ProfileManager().save_profile(profile)
            logger.info(f"[bold green] Resume imported for {profile.contact_info.full_name}[/bold green]")

        from src.jobs.finder import JobFinder
        from src.agents.orchestrator import ApplicationOrchestrator

        logger.info("[bold cyan]1. Discovering online job openings...[/bold cyan]")
        finder = JobFinder.create_multi_source_finder()
        finder.discover_jobs(query=args.search, location=args.location)

        logger.info("[bold cyan]2. Analyzing JDs, Matching, Tailoring Resumes & Applying in Browser...[/bold cyan]")
        orch = ApplicationOrchestrator()
        result = orch.run_pipeline()
        logger.info(f"[bold green] Autonomous Workflow Complete: {result}[/bold green]")
        return

    if args.search_rag:
        from src.rag.retriever import CandidateRAGStore
        rag = CandidateRAGStore()
        snippets = rag.retrieve_relevant_context(args.search_rag, top_k=3)
        logger.info(f"[bold cyan] Top RAG Evidence Snippets for: '{args.search_rag}'[/bold cyan]")
        for i, snip in enumerate(snippets, 1):
            logger.info(f"\n[bold green]Snippet #{i}:[/bold green]\n{snip}")
        return

    if args.ui:
        from src.ui.app import run_dashboard_server
        run_dashboard_server(port=args.port)
        return

    if args.discover_jobs:
        from src.jobs.finder import JobFinder
        finder = JobFinder.create_multi_source_finder()
        jobs = finder.discover_jobs(query=args.search, location=args.location, time_range=args.time_range)
        logger.info(f"[bold green] Discovery finished! Found and stored {len(jobs)} unique jobs (Recency: {args.time_range}).[/bold green]")
        return

    if args.apply_url:
        from src.automation.pilot import PilotRunner
        runner = PilotRunner()
        res = runner.run_pilot_on_url(args.apply_url, is_live_submission=args.live)
        logger.info(f"[bold green] Pilot Execution Complete: {res}[/bold green]")
        return

    if args.dry_run_test:
        import subprocess
        logger.info("[bold cyan]Running End-to-End Dry-Run Test Suite...[/bold cyan]")
        res = subprocess.run([sys.executable, "-m", "pytest", "tests/e2e/test_dry_run_pipeline.py", "-v"])
        if res.returncode == 0:
            logger.info("[bold green] End-to-End Dry-Run Test Suite Passed Successfully![/bold green]")
        else:
            logger.error("[bold red] End-to-End Dry-Run Test Suite Failed.[/bold red]")
        return

    if args.send_test_notification:
        from src.notifications.notifier import NotificationManager
        NotificationManager.notify_human_intervention("TestCorp AI", "Senior Python Engineer", "Test Alert Checkpoint")
        NotificationManager.notify_application_status("TestCorp AI", "Senior Python Engineer", "READY_TO_SUBMIT")
        NotificationManager.notify_daily_summary(discovered=5, qualified=2, submitted=1, skipped=3)
        logger.info("[bold green] Test notifications dispatched successfully.[/bold green]")
        return

    if args.show_history:
        from src.database.audit import AuditManager
        from rich.table import Table
        from rich.console import Console
        audit = AuditManager()
        history = audit.get_application_history()
        console = Console()
        table = Table(title="Application Tracking History")
        table.add_column("ID", justify="right", style="cyan")
        table.add_column("Company", style="magenta")
        table.add_column("Title", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Match Score", justify="right")
        table.add_column("Decision")
        table.add_column("Applied At", style="blue")

        for row in history:
            score_str = f"{row['match_score']}/100" if row['match_score'] is not None else "-"
            table.add_row(
                str(row["job_id"]),
                row["company"],
                row["title"],
                row["status"],
                score_str,
                row["decision"] or "-",
                row["applied_at"] or "-"
            )
        console.print(table)
        return

    if args.show_events:
        from src.database.audit import AuditManager
        from rich.table import Table
        from rich.console import Console
        audit = AuditManager()
        events = audit.get_application_events(args.show_events)
        console = Console()
        table = Table(title=f"Lifecycle Events for Job ID {args.show_events}")
        table.add_column("Event ID", justify="right", style="cyan")
        table.add_column("Event Type", style="magenta")
        table.add_column("Timestamp", style="green")
        table.add_column("Payload Details", style="white")

        for e in events:
            table.add_row(
                str(e["event_id"]),
                e["event_type"],
                str(e["timestamp"]),
                str(e["payload"])
            )
        console.print(table)
        return

    if args.export_audit:
        from src.database.audit import AuditManager
        audit = AuditManager()
        if args.export_audit == "json":
            path = audit.export_audit_log_to_json()
        else:
            path = audit.export_audit_log_to_csv()
        logger.info(f"[bold green] Audit export generated at: {path}[/bold green]")
        return

    if args.run_agent:
        from src.agents.orchestrator import ApplicationOrchestrator
        orchestrator = ApplicationOrchestrator()
        result = orchestrator.run_pipeline()
        logger.info(f"[bold green] Agent execution result: {result}[/bold green]")
        return

    if args.answer_question:
        from src.agents.answer_agent import ApplicationAnswerAgent
        agent = ApplicationAnswerAgent()
        out = agent.answer_question(args.answer_question)
        status_str = "[green]VERIFIED[/green]" if out.is_known else "[yellow]MANUAL REVIEW NEEDED[/yellow]"
        logger.info(f"Question: {out.question}")
        logger.info(f"Answer [{status_str}]: {out.answer}")
        return

    if args.approve_answer:
        from src.agents.answer_agent import ApplicationAnswerAgent
        q, a = args.approve_answer
        agent = ApplicationAnswerAgent()
        agent.record_user_approved_answer(q, a)
        logger.info(f"[bold green] Saved user-approved answer for '{q}' -> '{a}'[/bold green]")
        return

    if args.tailor_resumes:
        from src.agents.resume_agent import ResumeTailorAgent
        agent = ResumeTailorAgent()
        logger.info("[bold cyan]Running Resume Tailoring Engine...[/bold cyan]")
        paths = agent.tailor_all_pending_jobs()
        logger.info(f"[bold green] Resume Tailoring complete! {len(paths)} tailored PDF resumes generated and updated to RESUME_READY state.[/bold green]")
        for p in paths:
            logger.info(f" - Tailored PDF: {p}")
        return

    if args.match_jobs:
        from src.agents.match_agent import MatchAgent
        agent = MatchAgent()
        logger.info("[bold cyan]Running Qualification & Match Engine...[/bold cyan]")
        evals = agent.evaluate_all_pending_jobs()
        logger.info(f"[bold green] Match Engine complete! {len(evals)} jobs evaluated.[/bold green]")
        for e in evals:
            logger.info(f" - Score: {e.overall_score}/100 ({e.decision}) | Matched Skills: {', '.join(e.matched_skills)}")
        return

    if args.analyze_jobs:
        from src.agents.jd_agent import JDAgent
        agent = JDAgent()
        logger.info("[bold cyan]Running JD Analysis...[/bold cyan]")
        analyzed = agent.analyze_all_pending_jobs()
        logger.info(f"[bold green] JD Analysis complete! {len(analyzed)} jobs analyzed and updated to ANALYZED state.[/bold green]")
        for req in analyzed:
            logger.info(f" - {req.title} at {req.company} | Skills: {', '.join(req.required_skills)}")
        return

    if args.discover_jobs:
        from src.jobs.finder import JobFinder
        finder = JobFinder()
        logger.info("[bold cyan]Running Job Discovery...[/bold cyan]")
        new_jobs = finder.discover_jobs()
        logger.info(f"[bold green] Discovery complete! {len(new_jobs)} new unique jobs stored in SQLite database.[/bold green]")
        for j in new_jobs:
            logger.info(f" - {j.title} at {j.company} ({j.location}) -> URL: {j.url}")
        return

    if args.import_resume:
        from src.resume.profile import ProfileManager
        pm = ProfileManager()
        logger.info(f"Importing master resume from: {args.import_resume}...")
        profile = pm.import_master_resume(Path(args.import_resume))
        logger.info("[bold green] Resume imported and candidate profile created successfully![/bold green]")
        display_candidate_profile()
        return

    if args.show_profile:
        display_candidate_profile()
        return

    if args.edit_answer:
        from src.resume.profile import ProfileManager
        key, val = args.edit_answer
        pm = ProfileManager()
        pm.update_custom_answer(key, val)
        logger.info(f"[bold green] Saved custom answer: '{key}' -> '{val}'[/bold green]")
        return

    if args.check or len(sys.argv) == 1:
        run_health_check()

if __name__ == "__main__":
    main()
