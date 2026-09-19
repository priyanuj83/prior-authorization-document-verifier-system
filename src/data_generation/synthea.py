"""Load and index the Synthea extract."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional

from .paths import SYNTHEA_DIR


def parse_date(value: Optional[str]) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    value = str(value).strip()
    if not value:
        return None
    if "T" in value:
        value = value.split("T", 1)[0]
    return date.fromisoformat(value[:10])


def days_between(start: Optional[date], end: Optional[date]) -> Optional[int]:
    if start is None or end is None:
        return None
    return (end - start).days


class SyntheaStore:
    def __init__(self, root=None):
        self.root = root or SYNTHEA_DIR
        self.patients: Dict[str, dict] = {}
        self.payers: Dict[str, str] = {}
        self.conditions: Dict[str, List[dict]] = defaultdict(list)
        self.encounters: Dict[str, List[dict]] = defaultdict(list)
        self.encounters_by_id: Dict[str, dict] = {}
        self.careplans: Dict[str, List[dict]] = defaultdict(list)
        self.observation_counts: Dict[str, int] = defaultdict(int)
        self._load()

    def _load(self) -> None:
        with (self.root / "payers.csv").open() as f:
            for row in csv.DictReader(f):
                self.payers[row["Id"]] = row["NAME"]

        with (self.root / "patients.csv").open() as f:
            for row in csv.DictReader(f):
                self.patients[row["Id"]] = row

        with (self.root / "conditions.csv").open() as f:
            for row in csv.DictReader(f):
                self.conditions[row["PATIENT"]].append(row)

        with (self.root / "encounters.csv").open() as f:
            for row in csv.DictReader(f):
                self.encounters[row["PATIENT"]].append(row)
                self.encounters_by_id[row["Id"]] = row

        with (self.root / "careplans.csv").open() as f:
            for row in csv.DictReader(f):
                start = parse_date(row["START"])
                stop = parse_date(row["STOP"])
                rec = dict(row)
                rec["start_date"] = start
                rec["stop_date"] = stop
                rec["duration_days"] = days_between(start, stop)
                rec["is_pt"] = row.get("CODE") == "91251008"
                self.careplans[row["PATIENT"]].append(rec)

        obs_path = self.root / "observations.csv"
        if obs_path.exists():
            with obs_path.open() as f:
                reader = csv.DictReader(f)
                pid_field = "PATIENT" if "PATIENT" in (reader.fieldnames or []) else "Id"
                # observations.csv uses PATIENT in some extracts, otherwise column 2
                fields = reader.fieldnames or []
                patient_col = "PATIENT" if "PATIENT" in fields else fields[1]
                for row in reader:
                    self.observation_counts[row[patient_col]] += 1

    def patient(self, patient_id: str) -> dict:
        rec = self.patients.get(patient_id)
        if rec is None:
            raise KeyError(f"Unknown Synthea patient: {patient_id}")
        return rec

    def conditions_for(self, patient_id: str) -> List[dict]:
        return self.conditions.get(patient_id, [])

    def encounters_for(self, patient_id: str) -> List[dict]:
        return self.encounters.get(patient_id, [])

    def careplans_for(self, patient_id: str) -> List[dict]:
        return self.careplans.get(patient_id, [])

    def pt_careplans(self, patient_id: str) -> List[dict]:
        return [c for c in self.careplans_for(patient_id) if c["is_pt"]]

    def has_condition(self, patient_id: str, description: str) -> bool:
        return any(c["DESCRIPTION"] == description for c in self.conditions_for(patient_id))

    def first_condition(self, patient_id: str, description: str) -> Optional[dict]:
        matches = [c for c in self.conditions_for(patient_id) if c["DESCRIPTION"] == description]
        if not matches:
            return None
        matches.sort(key=lambda c: c["START"])
        return matches[0]

    def patients_with_condition(self, description: str) -> List[str]:
        found = []
        for pid, rows in self.conditions.items():
            if any(r["DESCRIPTION"] == description for r in rows):
                found.append(pid)
        return found

    def chart_totals(self, patient_id: str) -> dict:
        return {
            "conditions_lifetime": len(self.conditions_for(patient_id)),
            "encounters_lifetime": len(self.encounters_for(patient_id)),
            "observations_lifetime": int(self.observation_counts.get(patient_id, 0)),
            "careplans_lifetime": len(self.careplans_for(patient_id)),
        }

    def payer_name(self, payer_id: Optional[str]) -> str:
        if not payer_id:
            return "Unknown"
        return self.payers.get(payer_id, "Unknown")
