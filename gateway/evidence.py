"""Append-only event evidence. Simulation and hardware runs are labelled."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time


class Evidence:
    def __init__(self, directory, simulated):
        label = "simulation" if simulated else "hardware"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self.path = Path(directory) / f"{stamp}-{label}"
        self.path.mkdir(parents=True, exist_ok=False)
        self.simulated = simulated
        self.events = (self.path / "events.jsonl").open("w", encoding="utf-8")
        self.csv_file = (self.path / "parts.csv").open("w", newline="", encoding="utf-8")
        self.csv = csv.DictWriter(self.csv_file, fieldnames=["batch_id", "part_id", "verdict", "job_id"])
        self.csv.writeheader()
        self.recent = []
        self.record("run_started", mode=label)

    def record(self, event, **details):
        def safe_json(value):
            if isinstance(value, dict):
                return {key: (f"0x{item:016x}" if key == "session" and isinstance(item, int)
                              else safe_json(item)) for key, item in value.items()}
            if isinstance(value, list):
                return [safe_json(item) for item in value]
            return value
        item = {"utc": datetime.now(timezone.utc).isoformat(), "monotonic_s": time.monotonic(),
                "simulation": self.simulated, "event": event, **safe_json(details)}
        self.events.write(json.dumps(item) + "\n")
        self.events.flush()
        self.recent = (self.recent + [item])[-80:]

    def part(self, batch_id, part_id, verdict, job_id):
        self.csv.writerow(dict(batch_id=batch_id, part_id=part_id, verdict=verdict, job_id=job_id))
        self.csv_file.flush()

    def close(self):
        self.events.close()
        self.csv_file.close()
