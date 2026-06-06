"""Approval request storage for JARVIS safety gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
import json

from backend.agent.action_schema import Action
from backend.security.policy import PolicyDecision


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass(slots=True)
class ApprovalRequest:
    id: str
    action: Dict[str, Any]
    decision: Dict[str, Any]
    command: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        data = dict(data)
        data["status"] = ApprovalStatus(data.get("status", ApprovalStatus.PENDING))
        return cls(**data)


class ApprovalManager:
    """File-backed approval queue.

    The API server and headless agent can both see the same pending approvals via
    `data/security/approvals.json`. This is intentionally simple and robust for
    local-first operation.
    """

    def __init__(self, approval_file: str = "data/security/approvals.json"):
        self.approval_file = Path(approval_file)
        self.approval_file.parent.mkdir(parents=True, exist_ok=True)

    def create(self, action: Action, decision: PolicyDecision, command: str = "") -> ApprovalRequest:
        request = ApprovalRequest(
            id=f"approval_{uuid4().hex[:12]}",
            action=action.to_dict(),
            decision=decision.to_dict(),
            command=command,
        )
        requests = self._load_all()
        requests.append(request)
        self._save_all(requests)
        return request

    def list(self, status: Optional[ApprovalStatus | str] = None) -> List[ApprovalRequest]:
        requests = self._load_all()
        if status is None:
            return requests
        status_enum = ApprovalStatus(status)
        return [req for req in requests if req.status == status_enum]

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        return next((req for req in self._load_all() if req.id == approval_id), None)

    def approve(self, approval_id: str, resolved_by: str = "user", note: str = "") -> ApprovalRequest:
        return self._resolve(approval_id, ApprovalStatus.APPROVED, resolved_by, note)

    def deny(self, approval_id: str, resolved_by: str = "user", note: str = "") -> ApprovalRequest:
        return self._resolve(approval_id, ApprovalStatus.DENIED, resolved_by, note)

    def is_approved(self, approval_id: str) -> bool:
        req = self.get(approval_id)
        return bool(req and req.status == ApprovalStatus.APPROVED)

    def _resolve(self, approval_id: str, status: ApprovalStatus, resolved_by: str, note: str) -> ApprovalRequest:
        requests = self._load_all()
        for idx, req in enumerate(requests):
            if req.id == approval_id:
                req.status = status
                req.resolved_at = datetime.now().isoformat()
                req.resolved_by = resolved_by
                req.resolution_note = note
                requests[idx] = req
                self._save_all(requests)
                return req
        raise KeyError(f"Approval not found: {approval_id}")

    def _load_all(self) -> List[ApprovalRequest]:
        if not self.approval_file.exists():
            return []
        try:
            data = json.loads(self.approval_file.read_text(encoding="utf-8"))
            return [ApprovalRequest.from_dict(item) for item in data]
        except Exception:
            # Preserve corrupt file for debugging and start a new queue.
            corrupt = self.approval_file.with_suffix(".corrupt.json")
            try:
                self.approval_file.rename(corrupt)
            except Exception:
                pass
            return []

    def _save_all(self, requests: List[ApprovalRequest]) -> None:
        self.approval_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.approval_file.with_suffix(".tmp")
        tmp.write_text(json.dumps([req.to_dict() for req in requests], indent=2), encoding="utf-8")
        tmp.replace(self.approval_file)
