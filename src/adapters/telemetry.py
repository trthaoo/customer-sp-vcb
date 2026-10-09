"""
PostHog Backend Telemetry & Event Tracking Module.

Provides safe capture of backend events (e.g. webhook received, message processed,
handover triggered) without requiring posthog to be installed.
If posthog is installed and POSTHOG_API_KEY is configured, events are dispatched.
Otherwise, operations safely no-op.
"""
import logging
from typing import Optional, Dict, Any
from src.config import POSTHOG_API_KEY, POSTHOG_HOST

logger = logging.getLogger("posthog_telemetry")

_posthog_client = None

class _NoOpPostHog:
    def capture(self, *args, **kwargs):
        pass

    def identify(self, *args, **kwargs):
        pass

    def shutdown(self):
        pass

def get_telemetry():
    global _posthog_client
    if _posthog_client is not None:
        return _posthog_client

    if not POSTHOG_API_KEY:
        _posthog_client = _NoOpPostHog()
        return _posthog_client

    try:
        import posthog
        posthog.api_key = POSTHOG_API_KEY
        posthog.host = POSTHOG_HOST
        posthog.debug = False
        _posthog_client = posthog
        logger.info(f"PostHog backend telemetry client initialized (host: {POSTHOG_HOST})")
    except ImportError:
        logger.info("posthog Python library not installed; backend telemetry running in no-op mode.")
        _posthog_client = _NoOpPostHog()
    except Exception as e:
        logger.warning(f"Failed to initialize PostHog backend client: {e}")
        _posthog_client = _NoOpPostHog()

    return _posthog_client

def capture_event(distinct_id: str, event_name: str, properties: Optional[Dict[str, Any]] = None):
    """Convenience helper to safely capture an event to PostHog."""
    try:
        client = get_telemetry()
        client.capture(distinct_id=distinct_id, event=event_name, properties=properties or {})
    except Exception as e:
        logger.debug(f"Error capturing event {event_name}: {e}")
