"""Load the local candidate and curriculum JSON data."""

import json
from pathlib import Path
from typing import Any


DATA_DIRECTORY = Path(__file__).parent / "data"


def _load_json(filename: str) -> dict[str, Any]:
    """Load one JSON file from the local data directory."""
    file_path = DATA_DIRECTORY / filename
    with file_path.open(encoding="utf-8") as data_file:
        return json.load(data_file)


candidates_data = _load_json("candidates.json")
curriculum_data = _load_json("curriculum.json")


def find_candidate(candidate_id: str) -> dict[str, Any] | None:
    """Find a candidate by the ID stored in member.id."""
    for candidate in candidates_data["candidates"]:
        if candidate["member"]["id"] == candidate_id:
            return candidate

    return None


def get_curriculum_by_day(day_number: int) -> dict[str, Any] | None:
    """Find curriculum information for one day number."""
    for day in curriculum_data["days"]:
        if day["day"] == day_number:
            return day

    return None