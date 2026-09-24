from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, SecretStr

from app.services.mt5_service import MT5Service

router = APIRouter(prefix="/mt5", tags=["mt5"])


class ConnectRequest(BaseModel):
    login: int | None = None
    password: SecretStr | None = None
    server: str | None = None


@router.post("/connect")
def connect_mt5(request: ConnectRequest):
    pwd = request.password.get_secret_value() if request.password else None
    try:
        MT5Service.connect(request.login, pwd, request.server)
        return {"message": "Connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to MT5: {str(e)}")


@router.post("/disconnect")
def disconnect_mt5():
    MT5Service.disconnect()
    return {"message": "Disconnected successfully"}


@router.get("/account")
def get_account_info():
    try:
        info = MT5Service.get_account_info()
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get account info: {str(e)}")
