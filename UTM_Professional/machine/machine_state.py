from enum import Enum, auto

class MachineState(Enum):
    IDLE = auto()
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    HOLDING = auto()
    RETURNING = auto()
    COMPLETED = auto()
    EMERGENCY_STOP = auto()
    COMMUNICATION_LOST = auto()
    FAULT = auto()
    CALIBRATION = auto()
    SERVICE_MODE = auto()
