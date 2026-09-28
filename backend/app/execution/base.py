from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models import ApprovedOrder, ExecutionResult, Position, AccountSnapshot, Quote

class ExecutionAdapter(ABC):
    @abstractmethod
    def submit_order(self, order: ApprovedOrder) -> ExecutionResult:
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        pass

    @abstractmethod
    def get_account_snapshot(self) -> AccountSnapshot:
        pass
        
    @abstractmethod
    def heartbeat(self) -> bool:
        pass
        
    @abstractmethod
    def kill_switch(self) -> None:
        pass
