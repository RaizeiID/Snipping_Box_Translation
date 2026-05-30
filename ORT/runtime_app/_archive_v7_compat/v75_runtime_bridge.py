"""Compatibility wrapper kept for old external imports only.

ORT Translation v7.6 active runtime uses runtime_bridge.py.
"""
from runtime_bridge import RuntimeBridge, UnifiedRuntimeBridge
V71RuntimeBridge = RuntimeBridge
V72RuntimeBridge = RuntimeBridge
V73RuntimeBridge = RuntimeBridge
V75RuntimeBridge = RuntimeBridge
CORE_SLOTS = getattr(__import__('runtime_bridge'), 'CORE_SLOTS')
CoreSlot = getattr(__import__('runtime_bridge'), 'CoreSlot')
