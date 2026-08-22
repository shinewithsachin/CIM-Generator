"""
Data-retention sweep: deletes sessions (and their uploads/vector rows/PDFs)
older than RETENTION_DAYS, plus any chart PNG in outputs/ older than the
same window (chart files aren't attributable to a session by name — see
main.py's delete_session comment — so they're swept purely by age here).

Run on a schedule (cron / Windows Task Scheduler), e.g. daily:
    cd backend && python scripts/purge_expired_sessions.py
"""
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database as db
from config import settings
from rag_service import RAGService


def main() -> None:
    db.init_db()
    expired = db.get_expired_sessions(settings.retention_days)
    print(f"Found {len(expired)} session(s) older than {settings.retention_days} days.")

    for row in expired:
        session_id, owner_id, pdf_path = row["id"], row["owner_id"], row["pdf_path"]
        try:
            rag = RAGService(session_id=session_id, tenant_id=owner_id)
            rag.delete_collection()
        except Exception as e:
            print(f"  [{session_id}] vector cleanup skipped: {e}")

        upload_dir = os.path.join(settings.upload_dir, session_id)
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)

        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)

        db.delete_session_ownership(session_id)
        db.delete_session_row(session_id)
        print(f"  Purged session {session_id}")

    cutoff = time.time() - settings.retention_days * 86400
    output_dir = Path(settings.output_dir)
    swept = 0
    if output_dir.exists():
        for chart_file in output_dir.glob("chart_*.png"):
            if chart_file.stat().st_mtime < cutoff:
                chart_file.unlink(missing_ok=True)
                swept += 1
    print(f"Swept {swept} stale chart PNG(s).")


if __name__ == "__main__":
    main()
