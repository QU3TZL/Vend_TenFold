from enum import Enum
from datetime import datetime
import logging
import json
import uuid

class StateTransition(Enum):
    VISITOR_TO_AUTH = "VISITOR → AUTH"
    AUTH_TO_PAYMENT = "AUTH → PAYMENT"
    PAYMENT_TO_DRIVE = "PAYMENT → DRIVE"
    DRIVE_TO_ACTIVE = "DRIVE → ACTIVE"
    ACTIVE_TO_ERROR = "ACTIVE → ERROR"
    ANY_TO_ERROR = "* → ERROR"

class StateLogger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized: return
        
        # Single logger for all events
        self.logger = logging.getLogger('state')
        self._setup_logger()
        self._initialized = True

    def _setup_logger(self):
        # Single formatter for consistent output
        formatter = logging.Formatter('\n%(message)s | %(asctime)s\n')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _format_details(self, details: dict) -> str:
        if not details:
            return ""
        return "\n    " + "\n    ".join(f"{k}: {v}" for k, v in details.items())

    def log_event(self, category: str, action: str, details: dict = None):
        """Unified logging method for all events"""
        if details is None:
            details = {}
            
        # Create a structured log message
        msg = f"{category}: {action}{self._format_details(details)}"
        self.logger.info(msg)

    def state_change(self, transition: StateTransition, user_id: str, success: bool = True, details: dict = None):
        status = "✅" if success else "❌"
        self.log_event(
            category="State",
            action=f"{status} {transition.value}",
            details={"user_id": user_id, **(details or {})}
        )

    def auth_event(self, action: str, details: dict):
        self.log_event(
            category="🔐 Auth",
            action=action,
            details=details
        )

    def drive_event(self, action: str, details: dict):
        self.log_event(
            category="📁 Drive",
            action=action,
            details=details
        )

    def db_event(self, action: str, details: dict):
        self.log_event(
            category="💾 DB",
            action=action,
            details=details
        )

    def error(self, category: str, error_msg: str, details: dict = None):
        self.log_event(
            category=f"❌ {category}",
            action=error_msg,
            details=details
        )

    def history_data(self, transaction_id: str, internal_user_id: str, from_state: str, to_state: str, transition_reason: str, metadata: dict, created_at: datetime):
        # Human readable log
        hr_msg = f"🕒 History: {from_state} → {to_state}\n  user: {internal_user_id}\n  reason: {transition_reason}\n  metadata: {json.dumps(metadata, indent=2)}"
        self.logger.info(hr_msg)

        # Technical log
        tech_msg = f"""history_data:
  transaction_id: {transaction_id}
  internal_user_id: {internal_user_id}
  from_state: {from_state}
  to_state: {to_state}
  transition_reason: {transition_reason}
  metadata: {json.dumps(metadata, indent=2)}
  created_at: {created_at}"""
        self.logger.debug(tech_msg) 