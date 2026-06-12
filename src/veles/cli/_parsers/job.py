"""Parser for `veles job {add,list,show,pause,resume,trigger,remove,history,tick}`."""

from __future__ import annotations

import argparse

from veles.cli._parsers._common import add_common_run_flags, add_project_root_flag


def register(sub: argparse._SubParsersAction) -> None:
    job = sub.add_parser(
        "job",
        help="Manage scheduled agent jobs.",
    )
    add_project_root_flag(job)
    job_sub = job.add_subparsers(dest="job_command", required=True)

    j_add = job_sub.add_parser("add", help="Create a new scheduled job.")
    j_add.add_argument("--name", required=True, help="Job name (free-form label).")
    j_add.add_argument(
        "--schedule", required=True, help='Cron expr, "<N><s|m|h|d>", or ISO timestamp.'
    )
    j_add.add_argument("--prompt", required=True, help="Prompt to send to the agent on each tick.")
    j_add.add_argument(
        "--repeat", type=int, default=None, metavar="N", help="Stop after N successful runs."
    )
    j_add.add_argument(
        "--context-from",
        dest="context_from",
        default=None,
        metavar="JOB_ID",
        help="Prefix this job's prompt with the previous output of JOB_ID.",
    )
    j_add.add_argument(
        "--deliver-to",
        dest="deliver_to",
        default=None,
        metavar="TARGET",
        help='DeliveryTarget spec: "local" | "origin" | "<platform>:<chat_id>".',
    )

    job_list = job_sub.add_parser("list", help="List all jobs (most-recent first).")
    job_list.add_argument("--json", action="store_true", help="Output the job list as JSON.")

    job_show = job_sub.add_parser("show", help="Print a single job as JSON.")
    job_show.add_argument("id", help="Job id.")

    job_pause = job_sub.add_parser("pause", help="Disable a job until resumed.")
    job_pause.add_argument("id", help="Job id.")

    job_resume = job_sub.add_parser("resume", help="Re-enable a paused job.")
    job_resume.add_argument("id", help="Job id.")

    job_trigger = job_sub.add_parser(
        "trigger", help="Force a job to run on the next tick (sets next_run_at=now)."
    )
    job_trigger.add_argument("id", help="Job id.")

    job_remove = job_sub.add_parser("remove", help="Delete a job and its history.")
    job_remove.add_argument("id", help="Job id.")

    job_history = job_sub.add_parser("history", help="Show recent runs of a job.")
    job_history.add_argument("id", help="Job id.")
    job_history.add_argument(
        "--limit", type=int, default=20, help="Max runs to show (default 20)."
    )

    job_tick = job_sub.add_parser(
        "tick",
        help="Synchronously run all due jobs once (one-shot, no daemon required).",
    )
    add_common_run_flags(job_tick)
