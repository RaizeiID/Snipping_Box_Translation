"""ORT Translation v7.9 runtime actions facade.

Canonical import layer for closed-loop runtime control.  It wraps
runtime_health_applier.py so active code no longer references old versioned names.
"""
from __future__ import annotations
from runtime_health_applier import RuntimeHealthApplier, RuntimeDirectives

RuntimeActions = RuntimeHealthApplier
__all__ = ["RuntimeActions", "RuntimeHealthApplier", "RuntimeDirectives"]
