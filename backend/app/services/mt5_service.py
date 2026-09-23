from typing import Any

import MetaTrader5 as mt5


class MT5Service:
    @staticmethod
    def connect(login: int | None = None, password: str | None = None, server: str | None = None) -> bool:
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            return False

        if login and password and server:
            authorized = mt5.login(login, password=password, server=server)
            if not authorized:
                print(f"failed to connect at account #{login}, error code: {mt5.last_error()}")
                return False
        return True

    @staticmethod
    def disconnect() -> None:
        mt5.shutdown()

    @staticmethod
    def get_account_info() -> dict[str, Any] | None:
        account_info = mt5.account_info()
        if account_info is None:
            return None
        return account_info._asdict()
