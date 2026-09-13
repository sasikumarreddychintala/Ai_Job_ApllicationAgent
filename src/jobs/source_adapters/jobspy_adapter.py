from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger


class JobSpyAdapter(BaseJobAdapter):
    _SITES = ['linkedin', 'indeed', 'glassdoor', 'google']

    def __init__(self, country: str = 'India', results_per_site: int = 20):
        super().__init__(source_name='jobspy')
        self.country = country
        self.results_per_site = results_per_site

    def fetch_jobs(self, query: str = '', location: str = '', time_range: str = '3d') -> List[RawJobListing]:
        try:
            from jobspy import scrape_jobs
        except ImportError:
            logger.info('[JobSpy] python-jobspy not installed.')
            return []
        hours_old = self._parse_hours(time_range)
        try:
            logger.info(f'[JobSpy] Scraping {self._SITES} query={query!r} location={location!r} hours={hours_old}')
            df = scrape_jobs(
                site_name=self._SITES, search_term=query,
                location=location or self.country,
                results_wanted=self.results_per_site,
                hours_old=hours_old, country_indeed=self.country,
                linkedin_fetch_description=True,
            )
        except Exception as e:
            logger.warning(f'[JobSpy] Scraping failed: {e}')
            return []
        if df is None or df.empty:
            return []
        jobs: List[RawJobListing] = []
        for _, row in df.iterrows():
            try:
                title = str(row.get('title', '') or '').strip()
                company = str(row.get('company', '') or '').strip()
                loc_val = str(row.get('location', 'Remote') or 'Remote').strip()
                desc = str(row.get('description', '') or '').strip()
                url = str(row.get('job_url', '') or '').strip()
                site = str(row.get('site', 'jobspy') or 'jobspy').strip()
                posted = str(row.get('date_posted', '') or '').strip()
                if not title or not company or not url:
                    continue
                if not desc:
                    desc = f'{title} at {company}. See: {url}'
                jobs.append(RawJobListing(
                    title=title, company=company, location=loc_val,
                    description=desc, url=url,
                    source=f'jobspy_{site}', posted_date=posted or None,
                ))
            except Exception as row_err:
                logger.debug(f'[JobSpy] Skipping row: {row_err}')
        logger.info(f'[JobSpy] Found {len(jobs)} jobs.')
        return jobs

    @staticmethod
    def _parse_hours(time_range: str) -> int:
        s = (time_range or '72h').lower().strip()
        if s.endswith('d'): return int(s[:-1]) * 24
        if s.endswith('h'): return int(s[:-1])
        return 72
