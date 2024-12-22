from typing import Dict, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class VisitorService:
    """Service to handle visitor state logic"""
    
    def __init__(self):
        self.allowed_transitions = ["AUTH", "PAYMENT"]
        self.required_fields = []  # No required fields for visitor state
        
    async def get_visitor_info(self) -> Dict:
        """Retrieve information for the visitor state"""
        return {
            "current_state": "VISITOR",
            "state_metadata": {
                "last_updated": datetime.utcnow().isoformat(),
                "message": "Welcome to TenFold! Please sign in to continue.",
                "allowed_transitions": self.allowed_transitions
            }
        }

    async def validate_transition(self, target_state: str, state_data: Dict) -> Tuple[bool, Optional[str]]:
        """Validate state transition from VISITOR"""
        try:
            # Check if transition is allowed
            if target_state not in self.allowed_transitions:
                return False, f"Invalid transition from VISITOR to {target_state}"
                
            # For VISITOR state, we don't need to validate any required fields
            # But we could add validation logic here if needed in the future
            
            return True, None
            
        except Exception as e:
            logger.error(f"Transition validation failed: {str(e)}")
            return False, str(e)

    async def transition_state(self, target_state: str, state_data: Dict) -> Tuple[bool, Dict]:
        """Handle the transition from VISITOR to another state"""
        try:
            # Validate the transition
            valid, error = await self.validate_transition(target_state, state_data)
            if not valid:
                return False, {"error": error}
                
            # Prepare transition metadata
            transition_metadata = {
                "from_state": "VISITOR",
                "to_state": target_state,
                "timestamp": datetime.utcnow().isoformat(),
                "state_data": state_data
            }
            
            return True, transition_metadata
            
        except Exception as e:
            logger.error(f"State transition failed: {str(e)}")
            return False, {"error": str(e)}

    async def get_state_requirements(self) -> Dict:
        """Get requirements for the VISITOR state"""
        return {
            "required_fields": self.required_fields,
            "allowed_transitions": self.allowed_transitions,
            "description": "Initial state for unknown users"
        }
