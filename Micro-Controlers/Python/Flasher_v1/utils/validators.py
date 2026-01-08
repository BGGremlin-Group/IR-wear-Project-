def validate_config(config: dict) -> tuple[bool, str]:
    """
    Validate configuration dictionary before sending to microcontroller
    
    Returns:
        (is_valid: bool, error_message: str)
    """
    try:
        # Validate camera duration
        if "camera_duration" in config:
            if not isinstance(config["camera_duration"], int):
                return False, "camera_duration must be integer"
            if not (1000 <= config["camera_duration"] <= 60000):
                return False, "camera_duration must be 1000-60000ms"
        
        # Validate data injection duration
        if "injection_duration" in config:
            if not isinstance(config["injection_duration"], int):
                return False, "injection_duration must be integer"
            if not (500 <= config["injection_duration"] <= 30000):
                return False, "injection_duration must be 500-30000ms"
        
        # Validate jitter range
        if "jitter_range" in config:
            if not isinstance(config["jitter_range"], (int, float)):
                return False, "jitter_range must be number"
            if not (0.0 <= config["jitter_range"] <= 0.5):
                return False, "jitter_range must be 0.0-0.5"
        
        # Validate max cycles
        if "max_cycles" in config:
            if not isinstance(config["max_cycles"], int):
                return False, "max_cycles must be integer"
            if not (1 <= config["max_cycles"] <= 9999):
                return False, "max_cycles must be 1-9999"
        
        # Validate targets
        if "targets" in config:
            if not isinstance(config["targets"], list):
                return False, "targets must be list"
            if len(config["targets"]) > 20:
                return False, "Maximum 20 targets allowed"
            for target in config["targets"]:
                if not isinstance(target, str) or len(target) > 32:
                    return False, "Target names must be strings <= 32 chars"
        
        # Validate pattern name
        if "pattern_name" in config:
            if not isinstance(config["pattern_name"], str):
                return False, "pattern_name must be string"
            if len(config["pattern_name"]) > 50:
                return False, "pattern_name too long"
        
        return True, ""
    
    except Exception as e:
        return False, f"Validation error: {e}"

def validate_pattern(pattern: dict) -> tuple[bool, str]:
    """
    Validate attack pattern structure
    
    Returns:
        (is_valid: bool, error_message: str)
    """
    try:
        required_fields = ["name", "sequence"]
        for field in required_fields:
            if field not in pattern:
                return False, f"Missing required field: {field}"
        
        if not isinstance(pattern["sequence"], list):
            return False, "sequence must be a list"
        
        if len(pattern["sequence"]) == 0:
            return False, "sequence cannot be empty"
        
        if len(pattern["sequence"]) > 100:
            return False, "sequence too long (max 100 phases)"
        
        for i, phase in enumerate(pattern["sequence"]):
            required_keys = ["group", "intensity", "duration_ms"]
            for key in required_keys:
                if key not in phase:
                    return False, f"Phase {i} missing key: {key}"
            
            if not isinstance(phase["group"], int) or not (0 <= phase["group"] <= 5):
                return False, f"Phase {i} group must be 0-5"
            
            if not isinstance(phase["intensity"], int) or not (0 <= phase["intensity"] <= 255):
                return False, f"Phase {i} intensity must be 0-255"
            
            if not isinstance(phase["duration_ms"], int) or not (1 <= phase["duration_ms"] <= 60000):
                return False, f"Phase {i} duration_ms must be 1-60000"
        
        if "repeat" in pattern:
            if not isinstance(pattern["repeat"], int) or not (1 <= pattern["repeat"] <= 100):
                return False, "repeat must be 1-100"
        
        return True, ""
    
    except Exception as e:
        return False, f"Pattern validation error: {e}"
