from __future__ import annotations

import argparse

from polio_api.core.database import SessionLocal, initialize_database
from polio_api.services.async_job_service import get_async_job, process_async_job, process_next_async_job
from polio_shared.paths import ensure_app_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="polio background worker")
    subparsers = parser.add_subparsers(dest="command")

    run_pending_parser = subparsers.add_parser("run-pending", help="Process the next queued async job.")
    run_pending_parser.add_argument("--all", action="store_true", help="Process all queued async jobs.")

    run_one_parser = subparsers.add_parser("run-job", help="Process one async job by id.")
    run_one_parser.add_argument("job_id", help="Async job id")

    args = parser.parse_args()

    ensure_app_directories()
    initialize_database()

    if args.command == "run-job":
        _run_one(args.job_id)
        return

    if args.command == "run-pending":
        _run_pending(process_all=args.all)
        return

    parser.print_help()


def _run_one(job_id: str) -> None:
    with SessionLocal() as session:
        job = process_async_job(session, job_id)
        if not job:
            print("Async job not found.")
            return
        print(f"Processed async job: {job.id} -> {job.status}")


def _run_pending(process_all: bool) -> None:
    while True:
        with SessionLocal() as session:
            job = process_next_async_job(session)
            if not job:
                print("No queued async jobs found.")
                return

            processed = get_async_job(session, job.id)
            print(f"Processed async job: {processed.id} -> {processed.status}")

        if not process_all:
            return


if __name__ == "__main__":
    main()
