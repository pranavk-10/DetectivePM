"""Run one full ingestion, enrichment and verification now: python scripts/run_once.py"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.logging_setup import configure_logging  # noqa: E402
from backend.pipeline.ingest import run_discovery  # noqa: E402
from backend.pipeline.recruiters import run_enrichment  # noqa: E402
from backend.pipeline.verify import run_verification  # noqa: E402
from backend.scheduler import TASK_DISCOVERY, run_locked  # noqa: E402

configure_logging()
summary = run_locked(TASK_DISCOVERY, lambda: run_discovery("manual"))
if summary is None:
    sys.exit("Another ingestion holds the lease, or this run failed.")
summary.pop("results", None)
print(json.dumps({"discovery": summary, "enrichment": run_enrichment(), "verification": run_verification()}, indent=2))
