"""Privacy and request-compatibility middleware for the UMAP endpoint.

The visualiser renders every point of the precomputed layout (all labs), so
without this the hover text on ``/api/plot/umap/`` exposes ``Case ID: <id>``
for cases the requesting user isn't allowed to see in HGQN's own Cases view.

The HGQN backend proxy (backend/routes/labs.js) already applies its own
"own lab, or superuser" rule -- the same one the cases grid uses to redact
internalCaseId -- and forwards the outcome as a plain ``can_view_case_ids``
boolean in the request body. This middleware trusts that flag rather than
re-deriving HGQN's auth model, and strips the ``Case ID:`` prefix from the
Plotly hover fields whenever it is not truthy.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

UMAP_PATH_SUFFIX = "/api/plot/umap/"

_PLACEHOLDER_CASE_IDS = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "not available",
    "null",
    "unknown",
}
_CASE_ID_KEYS = (
    "case_ID_paper",
    "case_id",
    "caseId",
    "case_id_hidden",
    "db_case_id",
    "id",
    "pk",
)
_SELECTED_OBJECT_KEYS = (
    "selected_case",
    "selectedCase",
    "selected_row",
    "selectedRow",
)
_CASE_ID_PREFIX_RE = re.compile(
    r"^\s*Case ID:\s*.*?(?:<br\s*/?>|$)",
    flags=re.IGNORECASE,
)


def normalize_case_id(value: Any) -> str | None:
    """Return a stable case identifier while rejecting UI placeholders."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None

    case_id = str(value).strip()
    if case_id.casefold() in _PLACEHOLDER_CASE_IDS:
        return None

    if case_id.endswith(".0") and case_id[:-2].isdigit():
        return case_id[:-2]
    return case_id


def _case_id_from_mapping(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in _CASE_ID_KEYS:
        case_id = normalize_case_id(value.get(key))
        if case_id:
            return case_id
    return None


def extract_selected_case_id(payload: Mapping[str, Any]) -> str | None:
    """Extract the hidden selected-case key independently of its UI label.

    New callers should send ``selected_case_id``. Compatibility fallbacks
    support a selected row object and a selected row index so the visualiser
    never has to rely on the de-identified value rendered in the cases table.
    """
    for key in ("selected_case_id", "selectedCaseId"):
        case_id = normalize_case_id(payload.get(key))
        if case_id:
            return case_id

    for key in _SELECTED_OBJECT_KEYS:
        case_id = _case_id_from_mapping(payload.get(key))
        if case_id:
            return case_id

    selected = payload.get("selected")
    case_id = _case_id_from_mapping(selected)
    if case_id:
        return case_id

    cases = payload.get("cases")
    index = payload.get("selected_index", payload.get("selectedIndex"))
    if isinstance(cases, Sequence) and not isinstance(cases, (str, bytes)):
        try:
            selected_row = cases[int(index)] if index is not None else None
        except (IndexError, TypeError, ValueError):
            selected_row = None
        case_id = _case_id_from_mapping(selected_row)
        if case_id:
            return case_id

    # Backward compatibility for callers that already send the real ID in
    # ``selected``. Placeholder strings such as "Not available" are ignored.
    return normalize_case_id(selected)


def payload_grants_case_id_access(payload: Mapping[str, Any]) -> bool:
    """Read the same-lab-or-superuser decision the HGQN backend already made.

    HGQN computes this using the same rule the cases table uses to redact
    internalCaseId (own lab, or superuser) and forwards the result as a plain
    boolean; the visualiser trusts it rather than re-deriving HGQN's auth model.
    """
    for key in ("can_view_case_ids", "canViewCaseIds"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return False


def request_can_view_case_ids(
    request: Any, payload: Mapping[str, Any] | None = None
) -> bool:
    """Allow identifiers for an authenticated staff user, or when the request
    payload carries HGQN's same-lab-or-superuser decision."""
    user = getattr(request, "user", None)
    if (
        user is not None
        and bool(getattr(user, "is_authenticated", False))
        and (
            bool(getattr(user, "is_staff", False))
            or bool(getattr(user, "is_superuser", False))
        )
    ):
        return True

    if payload is not None and payload_grants_case_id_access(payload):
        return True

    return False


def _redact_hover_value(value: Any) -> Any:
    if isinstance(value, str):
        return _CASE_ID_PREFIX_RE.sub("", value, count=1)
    if isinstance(value, list):
        return [_redact_hover_value(item) for item in value]
    return value


def redact_case_ids_from_figure(figure: MutableMapping[str, Any]) -> None:
    """Remove case IDs from Plotly hover fields in place."""
    traces = figure.get("data", [])
    if not isinstance(traces, list):
        return

    for trace in traces:
        if not isinstance(trace, MutableMapping):
            continue
        for key in ("hovertext", "text"):
            if key in trace:
                trace[key] = _redact_hover_value(trace[key])


def redact_plotly_json_response(response: Any) -> Any:
    """Redact both normal and legacy double-encoded Plotly JSON responses."""
    if getattr(response, "status_code", None) != 200:
        return response

    content_type = response.get("Content-Type", "")
    if "application/json" not in content_type:
        return response

    try:
        outer_payload = json.loads(response.content.decode(response.charset or "utf-8"))
        double_encoded = isinstance(outer_payload, str)
        figure = json.loads(outer_payload) if double_encoded else outer_payload
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return response

    if not isinstance(figure, MutableMapping):
        return response

    redact_case_ids_from_figure(figure)
    encoded_figure = json.dumps(figure, separators=(",", ":"))
    response.content = (
        json.dumps(encoded_figure).encode(response.charset or "utf-8")
        if double_encoded
        else encoded_figure.encode(response.charset or "utf-8")
    )
    return response


class UmapPrivacyMiddleware:
    """Inject the hidden selection key and redact identifiers for non-admins."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_umap_request = (
            request.method == "POST" and request.path.endswith(UMAP_PATH_SUFFIX)
        )
        payload = self._inject_selected_case_id(request) if is_umap_request else None

        response = self.get_response(request)

        if is_umap_request and not request_can_view_case_ids(request, payload):
            return redact_plotly_json_response(response)
        return response

    @staticmethod
    def _inject_selected_case_id(request: Any) -> Mapping[str, Any] | None:
        try:
            payload = json.loads(request.body)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None

        selected_case_id = extract_selected_case_id(payload)
        payload["selected"] = selected_case_id

        encoding = request.encoding or "utf-8"
        request._body = json.dumps(payload).encode(encoding)
        request.META["CONTENT_LENGTH"] = str(len(request._body))
        return payload
