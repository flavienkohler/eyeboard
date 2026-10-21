"""The saved-dashboards document: versions, migration, parsing and serialisation.

Versions:

* 1 - a bare JSON list of dashboards (the original format); the plot theme was
  stored under the key ``template``.
* 2 - ``{"schema_version": 2, "dashboards": [...]}``; the key is ``theme``.
"""

import copy
import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from eyeboard.dashboards.model import Dashboard

SCHEMA_VERSION = 2


@dataclass(slots=True)
class LoadResult:
    """What could be read from a saved-dashboards document."""

    dashboards: list[Dashboard] = field(default_factory=list)
    # Readable messages about everything that was not loaded.
    problems: list[str] = field(default_factory=list)
    # Raw entries that failed validation. They are not in ``dashboards``; callers
    # must back the file up before saving, otherwise they would be lost.
    skipped: list[Any] = field(default_factory=list)
    source_version: int = SCHEMA_VERSION
    # True when the document cannot be understood (for example written by a newer
    # version). Saving over it would destroy data, so callers must not.
    blocked: bool = False

    @property
    def migrated(self) -> bool:
        """Whether the document was in an older format than the current one."""
        return self.source_version < SCHEMA_VERSION


def migrate_v1_to_v2(entries: list[Any]) -> list[Any]:
    """Convert version 1 dashboards (a list) to version 2 entries.

    Only renames keys; validation happens afterwards, on the migrated data.
    """
    migrated = copy.deepcopy(entries)
    for dashboard in migrated:
        if not isinstance(dashboard, dict):
            continue
        plots = dashboard.get("plots")
        if not isinstance(plots, list):
            continue
        for plot in plots:
            if isinstance(plot, dict) and "template" in plot:
                plot.setdefault("theme", plot["template"])
                del plot["template"]
    return migrated


def _format_error(error: dict[str, Any]) -> str:
    """Render one pydantic error as ``path: message``."""
    path = ".".join(str(part) for part in error["loc"])
    return f"{path}: {error['msg']}" if path else str(error["msg"])


def describe_validation_error(exc: ValidationError) -> list[str]:
    """List the problems of a validation error as readable lines."""
    return [_format_error(error) for error in exc.errors()]


def _parse_entries(
    entries: list[Any],
    result: LoadResult,
    originals: list[Any] | None = None,
) -> None:
    """Validate each entry; keep the good ones, report and set aside the others.

    ``originals`` are the entries as found in the file (before migration); those
    are what gets set aside, so they match the file on disk.
    """
    originals = entries if originals is None else originals
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        label = f"Dashboard {index}"
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            label = f"Dashboard '{entry['name']}'"
        try:
            dashboard = Dashboard.model_validate(entry)
        except ValidationError as exc:
            result.problems.extend(
                f"{label}: {line}" for line in describe_validation_error(exc)
            )
            result.skipped.append(originals[index - 1])
            continue
        if dashboard.id in seen_ids:
            result.problems.append(f"{label}: duplicate dashboard id '{dashboard.id}'.")
            result.skipped.append(originals[index - 1])
            continue
        seen_ids.add(dashboard.id)
        result.dashboards.append(dashboard)


def parse_document(raw: object) -> LoadResult:
    """Read a saved-dashboards document that was already decoded from JSON."""
    result = LoadResult()

    if isinstance(raw, list):
        result.source_version = 1
        _parse_entries(migrate_v1_to_v2(raw), result, originals=raw)
        return result

    if not isinstance(raw, dict):
        result.blocked = True
        result.problems.append(
            "The dashboards file must contain a JSON list or object."
        )
        return result

    version = raw.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        result.blocked = True
        result.problems.append("The dashboards file has no valid `schema_version`.")
        return result
    result.source_version = version
    if version > SCHEMA_VERSION:
        result.blocked = True
        result.problems.append(
            f"The dashboards file uses schema version {version}, but this version of "
            f"EyeBoard only understands up to {SCHEMA_VERSION}. Update EyeBoard; "
            "the file was left untouched."
        )
        return result

    entries = raw.get("dashboards")
    if not isinstance(entries, list):
        result.blocked = True
        result.problems.append("`dashboards` must be a list.")
        return result
    _parse_entries(entries, result)
    return result


def load_document_text(text: str) -> LoadResult:
    """Parse the text of a saved-dashboards file."""
    try:
        raw = json.loads(text)
    except ValueError as exc:
        result = LoadResult(blocked=True)
        result.problems.append(f"The dashboards file is not valid JSON: {exc}")
        return result
    return parse_document(raw)


def serialize_document(dashboards: list[Dashboard]) -> str:
    """Render dashboards as the current document format."""
    document = {
        "schema_version": SCHEMA_VERSION,
        "dashboards": [dashboard.model_dump(mode="json") for dashboard in dashboards],
    }
    return json.dumps(document, ensure_ascii=False, indent=2)


def parse_single_dashboard(raw: object) -> tuple[Dashboard | None, list[str]]:
    """Validate one dashboard coming from an import or from the JSON editor.

    Dashboards exported by earlier versions (``template`` instead of ``theme``)
    are accepted. Returns ``(dashboard, [])`` or ``(None, problems)``.
    """
    if not isinstance(raw, dict):
        return None, ["The dashboard must be a JSON object."]
    try:
        return Dashboard.model_validate(migrate_v1_to_v2([raw])[0]), []
    except ValidationError as exc:
        return None, describe_validation_error(exc)
