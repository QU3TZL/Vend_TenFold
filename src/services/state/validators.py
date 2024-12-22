from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

class StateValidator:
    """Validates state data and transitions"""
    
    def validate_required_fields(self, data: Dict, required_fields: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate that all required fields are present in the data"""
        try:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return False, f"Missing required fields: {', '.join(missing_fields)}"
            return True, None
        except Exception as e:
            logger.error(f"Field validation error: {str(e)}")
            return False, str(e)

    def validate_data_types(self, data: Dict, field_types: Dict[str, str]) -> Tuple[bool, Optional[str]]:
        """Validate that fields have correct data types"""
        try:
            type_map = {
                'string': str,
                'int': int,
                'float': float,
                'bool': bool,
                'dict': dict,
                'list': list
            }
            
            for field, expected_type in field_types.items():
                if field in data:
                    value = data[field]
                    if expected_type in type_map:
                        if not isinstance(value, type_map[expected_type]):
                            return False, f"Field '{field}' should be of type {expected_type}"
            return True, None
        except Exception as e:
            logger.error(f"Type validation error: {str(e)}")
            return False, str(e)

    def validate_state_transition(
        self,
        current_state: str,
        target_state: str,
        allowed_transitions: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """Validate if a state transition is allowed"""
        try:
            if target_state not in allowed_transitions:
                return False, f"Invalid transition from {current_state} to {target_state}"
            return True, None
        except Exception as e:
            logger.error(f"Transition validation error: {str(e)}")
            return False, str(e) 