import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.resume.validator import CandidateProfile
from src.resume.parser import extract_resume_text, parse_resume_with_ollama

class ProfileManager:
    """Manages master resume storage, candidate profile persistence, and field updates."""

    def __init__(
        self,
        profile_path: Path = settings.CANDIDATE_PROFILE_PATH,
        master_dir: Path = settings.MASTER_RESUME_PATH.parent
    ):
        self.profile_path = profile_path
        self.master_dir = master_dir
        self.master_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)

    def import_master_resume(self, file_path: Path) -> CandidateProfile:
        """
        Imports master resume file into immutable master storage,
        extracts text, parses into structured profile, and saves profile JSON & DB record.
        """
        source_path = Path(file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Master resume file not found at: {source_path}")

        # Copy to immutable master directory
        dest_filename = f"master_resume{source_path.suffix.lower()}"
        dest_path = self.master_dir / dest_filename
        shutil.copy2(source_path, dest_path)
        logger.info(f" Master resume stored immutably at: {dest_path}")

        # Extract text & parse with Ollama
        raw_text = extract_resume_text(dest_path)
        profile = parse_resume_with_ollama(raw_text)

        # Save profile JSON
        self.save_profile(profile)

        # Save record in SQLite DB
        self._record_in_db(raw_text, profile)

        return profile

    def save_profile(self, profile: CandidateProfile) -> None:
        """Saves CandidateProfile object to candidate_profile.json."""
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, indent=2, ensure_ascii=False)
        logger.info(f" Candidate profile saved to: {self.profile_path}")

    def load_profile(self) -> Optional[CandidateProfile]:
        """Loads verified CandidateProfile from JSON file."""
        if not self.profile_path.exists():
            logger.warning(f"No candidate profile found at {self.profile_path}")
            return None

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CandidateProfile(**data)
        except Exception as e:
            logger.error(f"Failed to load candidate profile from {self.profile_path}: {e}")
            return None

    def update_custom_answer(self, question_key: str, answer_value: str) -> CandidateProfile:
        """Updates pre-approved custom answer in the candidate profile."""
        profile = self.load_profile()
        if not profile:
            raise ValueError("Candidate profile does not exist yet. Please import master resume first.")

        profile.custom_answers[question_key] = answer_value
        self.save_profile(profile)
        logger.info(f" Updated custom answer for '{question_key}'.")
        return profile

    def _record_in_db(self, raw_text: str, profile: CandidateProfile) -> None:
        """Persists raw resume text & structured profile JSON into SQLite candidate_profile table."""
        try:
            conn = init_db()
            with conn:
                conn.execute(
                    "INSERT INTO candidate_profile (raw_text, profile_json) VALUES (?, ?)",
                    (raw_text, json.dumps(profile.model_dump()))
                )
            conn.close()
            logger.info(" Saved resume & candidate profile record to SQLite database.")
        except Exception as e:
            logger.error(f"Failed to record candidate profile in SQLite: {e}")

if __name__ == "__main__":
    pm = ProfileManager()
    profile = pm.load_profile()
    if profile:
        print(f"Loaded profile for: {profile.contact_info.full_name}")
    else:
        print("No profile loaded.")
