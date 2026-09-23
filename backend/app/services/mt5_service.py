import MetaTrader5 as mt5
from typing import Dict, Any, Optional

class MT5Service:
    @staticmethod
    def connect(login: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None) -> bool:
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            return False
            
        if login and password and server:
            authorized = mt5.login(login, password=password, server=server)
            if not authorized:
                print("failed to connect at account #{}, error code: {}".format(login, mt5.last_error()))
                return False
        return True

    @staticmethod
    def disconnect() -> None:
        mt5.shutdown()

    @staticmethod
    def get_account_info() -> Optional[Dict[str, Any]]:
        account_info = mt5.account_info()
        if account_info is None:
            return None
        return account_info._asdict()
