"""Calls the real public APIs. Run with: pytest -m live"""

import pytest

from backend.sources.ashby import AshbyConnector
from backend.sources.authorized_api import RemotiveConnector
from backend.sources.greenhouse import GreenhouseConnector
from backend.sources.lever import LeverConnector
from backend.sources.rss_feed import RssFeedConnector

pytestmark = pytest.mark.live

CASES = [
    (GreenhouseConnector, {"board": "groww", "company": "Groww"}),
    (LeverConnector, {"board": "cred", "company": "CRED"}),
    (AshbyConnector, {"board": "sarvam", "company": "Sarvam"}),
    (RemotiveConnector, {}),
    (RssFeedConnector, {"url": "https://weworkremotely.com/categories/remote-product-jobs.rss", "remote_feed": True}),
]


@pytest.mark.parametrize("connector_class, config", CASES, ids=[c[0].__name__ for c in CASES])
def test_connector_reads_real_records(connector_class, config):
    connector = connector_class(config)
    raws = connector.fetch_jobs()
    assert raws, "the source returned no records"
    jobs = [connector.normalize_job(raw) for raw in raws]
    valid = [job for job in jobs if job and not connector.validate_job(job)]
    assert len(valid) >= len(jobs) * 0.8, "most real records should normalize cleanly"
    assert all(job.application_url.startswith("http") for job in valid)
    assert connector.health_check().ok
