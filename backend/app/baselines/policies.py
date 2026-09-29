from abc import ABC, abstractmethod

from app.simulator.domain import ActionProposal, MarketObservation


class BaselinePolicy(ABC):
    @abstractmethod
    def predict(self, observation: MarketObservation) -> ActionProposal:
        pass

class AlwaysFlatPolicy(BaselinePolicy):
    def predict(self, observation: MarketObservation) -> ActionProposal:
        return ActionProposal(symbol=observation.symbol, target_weight=0.0)

class AlwaysLongPolicy(BaselinePolicy):
    def predict(self, observation: MarketObservation) -> ActionProposal:
        return ActionProposal(symbol=observation.symbol, target_weight=1.0)

class AlwaysShortPolicy(BaselinePolicy):
    def predict(self, observation: MarketObservation) -> ActionProposal:
        return ActionProposal(symbol=observation.symbol, target_weight=-1.0)

class SimpleMomentumPolicy(BaselinePolicy):
    def predict(self, observation: MarketObservation) -> ActionProposal:
        ret = observation.features.get('ret_1', 0.0)
        weight = 1.0 if ret > 0 else (-1.0 if ret < 0 else 0.0)
        return ActionProposal(symbol=observation.symbol, target_weight=weight)

class SimpleMeanReversionPolicy(BaselinePolicy):
    def predict(self, observation: MarketObservation) -> ActionProposal:
        ret = observation.features.get('ret_1', 0.0)
        weight = -1.0 if ret > 0 else (1.0 if ret < 0 else 0.0)
        return ActionProposal(symbol=observation.symbol, target_weight=weight)
