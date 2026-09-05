import re
from pathlib import Path
from typing import Optional, List
from playwright.sync_api import Page, ElementHandle
from src.utils.logger import logger

class FormFiller:
    """Dynamic form interaction engine for locating, filling, and uploading files on web application forms."""

    def __init__(self, page: Page):
        self.page = page

    def fill_text_field(self, field_name: str, value: str) -> bool:
        """Locates text input / textarea by label, placeholder, name, or ID and types value."""
        if not value:
            return False

        selectors = [
            f"input[name*='{field_name}' i]",
            f"input[id*='{field_name}' i]",
            f"input[placeholder*='{field_name}' i]",
            f"textarea[name*='{field_name}' i]",
            f"textarea[id*='{field_name}' i]",
            f"textarea[placeholder*='{field_name}' i]",
        ]

        # Try Playwright get_by_label
        import random
        try:
            lbl_locator = self.page.get_by_label(re.compile(field_name, re.IGNORECASE))
            if lbl_locator.count() > 0 and lbl_locator.first.is_visible():
                try:
                    # Natural human typing delay with micro-jitter
                    lbl_locator.first.press_sequentially(value, delay=random.randint(20, 50))
                except Exception:
                    lbl_locator.first.fill(value)
                logger.info(f" Filled field '{field_name}' via label.")
                return True
        except Exception:
            pass

        # Try explicit CSS selectors
        for sel in selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    try:
                        loc.first.press_sequentially(value, delay=random.randint(20, 50))
                    except Exception:
                        loc.first.fill(value)
                    logger.info(f" Filled field '{field_name}' via selector '{sel}'.")
                    return True
            except Exception:
                continue

        logger.debug(f"Could not locate text field for: '{field_name}'")
        return False

    def select_dropdown_option(self, field_name: str, option_text: str) -> bool:
        """Selects option in <select> dropdown element."""
        try:
            lbl_locator = self.page.get_by_label(re.compile(field_name, re.IGNORECASE))
            if lbl_locator.count() > 0 and lbl_locator.first.is_visible():
                lbl_locator.first.select_option(label=option_text)
                logger.info(f" Selected dropdown option '{option_text}' for '{field_name}'.")
                return True
        except Exception:
            pass

        selectors = [f"select[name*='{field_name}' i]", f"select[id*='{field_name}' i]"]
        for sel in selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.select_option(label=option_text)
                    logger.info(f" Selected dropdown option via selector '{sel}'.")
                    return True
            except Exception:
                continue

        logger.warning(f"Could not locate dropdown for: '{field_name}'")
        return False

    def upload_file(self, field_name: str, file_path: Path) -> bool:
        """Uploads file to <input type='file'>."""
        if not file_path.exists():
            logger.error(f"Upload file does not exist: {file_path}")
            return False

        try:
            # Check for input[type='file']
            file_inputs = self.page.locator("input[type='file']")
            if file_inputs.count() > 0:
                file_inputs.first.set_input_files(str(file_path))
                logger.info(f" Uploaded file '{file_path.name}' to input[type='file'].")
                return True
        except Exception as e:
            logger.warning(f"File upload failed ({e}).")

        return False

    def click_radio_or_checkbox(self, label_text: str) -> bool:
        """Checks radio or checkbox by visible label text."""
        try:
            loc = self.page.get_by_label(re.compile(label_text, re.IGNORECASE))
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.check()
                logger.info(f" Checked option for '{label_text}'.")
                return True
        except Exception:
            pass
        return False
