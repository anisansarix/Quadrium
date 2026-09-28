from abc import ABC, abstractmethod
import math
from app.domain.models import AccountSnapshot

class RewardModel(ABC):
    @abstractmethod
    def calculate_reward(self, previous_account: AccountSnapshot, current_account: AccountSnapshot) -> float:
        pass

class LogEquityChangeReward(RewardModel):
    """
    Deterministic default: Reward = log(current_equity / previous_equity)
    """
    def calculate_reward(self, previous_account: AccountSnapshot, current_account: AccountSnapshot) -> float:
        if previous_account.equity <= 0 or current_account.equity <= 0:
            return -1.0 # Penalize bankruptcy heavily
        return math.log(current_account.equity / previous_account.equity)
