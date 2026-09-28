from enum import Enum

from pydantic import BaseModel


class SLTriggerQuote(str, Enum):
    BID = "BID"
    ASK = "ASK"

class IntrabarFillPolicy(BaseModel):
    """
    Defines exactly how SL/TP are triggered within a deterministic backtest.
    
    Quote matching:
    - Long position SL is triggered by BID falling below SL
    - Long position TP is triggered by BID rising above TP
    - Short position SL is triggered by ASK rising above SL
    - Short position TP is triggered by ASK falling below TP
    
    If both SL and TP are triggered simultaneously (e.g. gap or wide OHLC bar),
    the policy determines which hits first, or requires tick data to resolve.
    For this deterministic phase, we require quote/tick level data.
    """
    require_tick_data: bool = True
    long_sl_trigger: SLTriggerQuote = SLTriggerQuote.BID
    long_tp_trigger: SLTriggerQuote = SLTriggerQuote.BID
    short_sl_trigger: SLTriggerQuote = SLTriggerQuote.ASK
    short_tp_trigger: SLTriggerQuote = SLTriggerQuote.ASK
