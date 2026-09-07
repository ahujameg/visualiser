"""Rebuild the UMAP layout for a lab (the slow ``redo`` path).

This runs as its own OS process, detached from any gunicorn worker, because
a full sparse-Resnik UMAP recompute has taken up to ~46h on the test server.
It must never be tied to an HTTP request's lifetime or a worker's timeout.

Invoked by plot_visualisation.views.start_umap_recompute via
``manage.py recompute_umap --payload <path> [--lock <path>]``, where the
payload file is a JSON object: {"lab": "<lab>", "cases": [...]}.
"""

import json
import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from plot_visualisation.figure1_part2 import generate_umap


class Command(BaseCommand):
    help = "Rebuild the UMAP layout for a lab (slow: can take tens of hours)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--payload",
            required=True,
            help="Path to a JSON file: {\"lab\": <lab>, \"cases\": [...]}",
        )
        parser.add_argument(
            "--lock",
            default=None,
            help="Lock file (written by the caller with this process's pid) "
                 "to remove once the recompute finishes, successfully or not.",
        )

    def handle(self, *args, **options):
        payload_path = options["payload"]
        lock_path = options.get("lock")
        try:
            try:
                with open(payload_path) as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                raise CommandError(f"Could not read payload {payload_path}: {exc}")

            lab = data.get("lab", "allLabs")
            cases = data.get("cases")
            if not isinstance(cases, list) or not cases:
                raise CommandError("payload['cases'] must be a non-empty list")

            all_cases = pd.DataFrame(cases)
            if "HPO_Term_IDs" in all_cases.columns:
                all_cases["HPO_Term_IDs"] = all_cases["HPO_Term_IDs"].fillna("unknown")

            self.stdout.write(f"recompute_umap: starting for lab={lab!r}, n_cases={len(all_cases)}")
            generate_umap(all_cases, lab, None, "redo")
            self.stdout.write(self.style.SUCCESS(f"recompute_umap: done for lab={lab!r}"))
        finally:
            # Always release the lock, whether we succeeded, raised, or the
            # payload was bad -- otherwise a failed run would permanently
            # block any future recompute for this lab (start_umap_recompute
            # treats a live pid at this lock path as "already running").
            if lock_path:
                try:
                    os.remove(lock_path)
                except OSError:
                    pass
            try:
                os.remove(payload_path)
            except OSError:
                pass
