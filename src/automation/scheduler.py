import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from config import settings
from src.utils.logger import logger
from src.jobs.finder import JobFinder
from src.agents.jd_agent import JDAgent
from src.agents.match_agent import MatchAgent
from src.agents.resume_agent import ResumeTailorAgent

class MorningJobScheduler:
    """
    Automated Background Scheduler for daily autonomous job discovery,
    JD match scoring, and tailored PDF resume compilation.
    """

    def __init__(self, schedule_time: str = "08:00"):
        self.schedule_time = schedule_time  # Format: "HH:MM" 24h
        self.enabled = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.last_run: Optional[str] = None
        self.last_summary: Dict[str, Any] = {}

    def start(self):
        """Starts the scheduler thread."""
        if self.enabled and self._thread and self._thread.is_alive():
            return
        self.enabled = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="MorningJobSchedulerThread")
        self._thread.start()
        logger.info(f"[SCHEDULER] Automated Morning Job Scheduler activated! Target daily run: {self.schedule_time}")

    def stop(self):
        """Stops the scheduler thread."""
        self.enabled = False
        self._stop_event.set()
        logger.info("[SCHEDULER] Automated Job Scheduler paused.")

    def run_now(self, query: str = "", location: str = "Bengaluru") -> Dict[str, Any]:
        """Executes the full discovery, scoring, and tailoring cycle immediately."""
        logger.info("[AUTOPILOT] Executing Multi-Role Job Discovery (AI, ML, Associate SWE, Data Analyst)...")
        start_time = datetime.now()

        # 1. Multi-source Discovery across all 10+ platforms with multi-role coverage
        finder = JobFinder.create_multi_source_finder()
        queries_to_run = [query] if query else [
            "Junior AI Engineer 0-2 years",
            "Associate Software Engineer 0-2 years",
            "Software Developer Python 0-2 years",
            "Python Backend Developer 0-2 years",
            "Junior Full Stack Developer 0-2 years",
            "Junior Data Analyst Python 0-2 years"
        ]
        discovered = []
        for q in queries_to_run:
            res = finder.discover_jobs(query=q, location=location, time_range="24h")
            discovered.extend(res)
        
        # 2. Fast JD Parsing
        jd_agent = JDAgent()
        analyzed = jd_agent.analyze_all_pending_jobs(limit=150)

        # 3. Match Evaluation & 100-Point Scoring
        match_agent = MatchAgent()
        evals = match_agent.evaluate_all_pending_jobs()

        # 4. Compile Tailored PDF Resumes for Qualified Matches
        tailor_agent = ResumeTailorAgent()
        tailored_paths = tailor_agent.tailor_all_pending_jobs()

        # 5. Check and Dispatch 7-Day Recruiter Follow-Up Reminders
        try:
            from src.outreach.followup_agent import followup_manager
            followup_manager.check_and_notify_daily_followups()
        except Exception as fe:
            logger.debug(f"Follow-up check notice: {fe}")

        self.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_summary = {
            "timestamp": self.last_run,
            "duration_sec": round((datetime.now() - start_time).total_seconds(), 2),
            "discovered_jobs": len(discovered),
            "analyzed_jobs": len(analyzed),
            "evaluated_matches": len(evals),
            "tailored_resumes": len(tailored_paths)
        }

        logger.info(
            f"[AUTOPILOT] Auto-Pilot Cycle Complete! Discovered: {len(discovered)} jobs | "
            f"Analyzed: {len(analyzed)} | Scored: {len(evals)} | Tailored Resumes: {len(tailored_paths)} in {self.last_summary['duration_sec']}s."
        )
        return self.last_summary

    def get_status(self) -> Dict[str, Any]:
        """Returns scheduler state, target time, and next run calculation."""
        next_run_str = self._calculate_next_run()
        return {
            "enabled": self.enabled,
            "schedule_time": self.schedule_time,
            "last_run": self.last_run,
            "next_run": next_run_str,
            "last_summary": self.last_summary
        }

    def _calculate_next_run(self) -> str:
        now = datetime.now()
        try:
            hour, minute = map(int, self.schedule_time.split(":"))
        except Exception:
            hour, minute = 8, 0

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target.strftime("%Y-%m-%d %H:%M:%S")

    def _run_loop(self):
        """Background loop that sleeps until the target time and triggers discovery."""
        while not self._stop_event.is_set():
            now = datetime.now()
            try:
                hour, minute = map(int, self.schedule_time.split(":"))
            except Exception:
                hour, minute = 8, 0

            # If current hour & minute match schedule, run discovery
            if now.hour == hour and now.minute == minute and (not self.last_run or not self.last_run.startswith(now.strftime("%Y-%m-%d %H:%M"))):
                try:
                    self.run_now()
                except Exception as e:
                    logger.error(f"Scheduler execution error: {e}")
                # Sleep 65 seconds so we don't trigger multiple times in the same minute
                time.sleep(65)
            else:
                # Sleep in short increments to allow graceful shutdown
                self._stop_event.wait(timeout=20)

# Global Scheduler Instance
scheduler = MorningJobScheduler(schedule_time="08:00")