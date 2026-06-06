"""JARVIS security package.

Security modules are lazy-exported so policy/approval tests can run without
importing optional runtime dependencies used by TrustManager.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ApprovalManager",
    "ApprovalRequest",
    "ApprovalStatus",
    "AuditEvent",
    "AuditLogger",
    "PolicyDecision",
    "PolicyDecisionType",
    "PolicyEngine",
    "TrustManager",
]


def __getattr__(name: str) -> Any:
    if name in {"ApprovalManager", "ApprovalRequest", "ApprovalStatus"}:
        from backend.security import approval

        return getattr(approval, name)
    if name in {"AuditLogger", "AuditEvent"}:
        from backend.security import audit_log

        return getattr(audit_log, name)
    if name in {"PolicyDecision", "PolicyDecisionType", "PolicyEngine"}:
        from backend.security import policy

        return getattr(policy, name)
    if name == "TrustManager":
        from backend.security.trust import TrustManager

        return TrustManager
    raise AttributeError(name)
