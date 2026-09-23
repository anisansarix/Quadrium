from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.mt5_service import MT5Service

router = APIRouter(prefix="/mt5", tags=["mt5"])

class ConnectRequest(BaseModel):
    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None

@router.post("/connect")
def connect_mt5(request: ConnectRequest):
    success = MT5Service.connect(request.login, request.password, request.server)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to connect to MT5")
    return {"message": "Connected successfully"}

@router.post("/disconnect")
def disconnect_mt5():
    MT5Service.disconnect()
    return {"message": "Disconnected successfully"}

@router.get("/account")
def get_account_info():
    info = MT5Service.get_account_info()
    if info is None:
        raise HTTPException(status_code=400, detail="Failed to get account info")
    return info
