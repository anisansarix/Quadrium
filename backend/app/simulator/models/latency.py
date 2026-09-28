from abc import ABC, abstractmethod
from datetime import datetime


class LatencyModel(ABC):
    @abstractmethod
    def add_latency(self, timestamp: datetime) -> datetime:
        pass

class ZeroLatencyModel(LatencyModel):
    def add_latency(self, timestamp: datetime) -> datetime:
        return timestamp
