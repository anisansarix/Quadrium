from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Any

from app.core.database import get_db_session
from app.models.db import LiveTradingSession
from app.services.live_trading_engine import LiveTradingEngine

router = APIRouter(prefix="/live", tags=["Live Trading"])

class StartLiveSessionRequest(BaseModel):
    experiment_id: str
    symbol: str
    timeframe: str
    config: dict[str, Any]

@router.post("/start")
async def start_session(req: StartLiveSessionRequest):
    async with get_db_session() as db:
        session = LiveTradingSession(
            experiment_id=req.experiment_id,
            symbol=req.symbol,
            timeframe=req.timeframe,
            initial_balance=25000.0,
            current_balance=25000.0,
            current_equity=25000.0,
            config=req.config,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        session_id = session.id
        
    try:
        await LiveTradingEngine.start_session(
            session_id=session_id,
            experiment_id=req.experiment_id,
            symbol=req.symbol,
            timeframe=req.timeframe,
            config=req.config
        )
    except Exception as e:
        async with get_db_session() as db:
            stmt = select(LiveTradingSession).where(LiveTradingSession.id == session_id)
            res = await db.execute(stmt)
            session = res.scalar_one_or_none()
            if session:
                session.status = "error"
                await db.commit()
        raise HTTPException(status_code=400, detail=str(e))
        
    return {"status": "success", "session_id": session_id}

@router.post("/{session_id}/stop")
async def stop_session(session_id: str):
    await LiveTradingEngine.stop_session(session_id)
    return {"status": "success"}

@router.get("/")
async def list_sessions():
    async with get_db_session() as db:
        stmt = select(LiveTradingSession).order_by(LiveTradingSession.created_at.desc())
        res = await db.execute(stmt)
        sessions = res.scalars().all()
        # Convert to dict to avoid serialization issues
        return [{"id": s.id, "experiment_id": s.experiment_id, "symbol": s.symbol, "timeframe": s.timeframe, "status": s.status, "current_equity": s.current_equity, "current_balance": s.current_balance, "created_at": s.created_at.isoformat(), "config": s.config} for s in sessions]

@router.get("/{session_id}")
async def get_session(session_id: str):
    async with get_db_session() as db:
        stmt = select(LiveTradingSession).where(LiveTradingSession.id == session_id)
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"id": session.id, "experiment_id": session.experiment_id, "symbol": session.symbol, "timeframe": session.timeframe, "status": session.status, "current_equity": session.current_equity, "current_balance": session.current_balance}

try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore[assignment]
    _MT5_AVAILABLE = False
import asyncio

if _MT5_AVAILABLE:
    @router.get("/mt5/account")
    async def get_account_info():
        def _fetch_acc():
            if not mt5.initialize():
                return None
            return mt5.account_info()

        acc = await asyncio.to_thread(_fetch_acc)
        if not acc:
            raise HTTPException(status_code=500, detail="Could not connect to MT5")

        return {
            "login": acc.login,
            "server": acc.server,
            "balance": acc.balance,
            "equity": acc.equity,
            "margin": acc.margin,
            "margin_free": acc.margin_free,
            "currency": acc.currency,
            "name": acc.name,
            "leverage": acc.leverage
        }

    @router.get("/{session_id}/positions")
    async def get_positions(session_id: str):
        # In a real scenario, we'd filter by the magic number or symbol of the session
        def _fetch_pos():
            if not mt5.initialize():
                return []
            positions = mt5.positions_get()
            if positions is None:
                return []
            return [{
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "time": p.time
            } for p in positions]

        positions = await asyncio.to_thread(_fetch_pos)
        return {"positions": positions}


@router.get("/{session_id}/history")
async def get_history(session_id: str):
    def _fetch_hist():
        if not mt5.initialize():
            return {"trades": [], "stats": {}}
            
        from datetime import datetime, timedelta
        
        date_to = datetime.now()
        date_from = date_to - timedelta(days=30)
        deals = mt5.history_deals_get(date_from, date_to)
        
        if deals is None:
            return {"trades": [], "stats": {}}
            
        trades = []
        total_trades = 0
        winning_trades = 0
        gross_profit = 0.0
        gross_loss = 0.0
        
        for d in reversed(deals):
            if d.entry in (1, 2):  # ENTRY_OUT or ENTRY_INOUT
                total_trades += 1
                if d.profit > 0:
                    winning_trades += 1
                    gross_profit += d.profit
                else:
                    gross_loss += abs(d.profit)
                    
                trades.append({
                    "id": f"T-{d.ticket}",
                    "date": datetime.fromtimestamp(d.time).strftime("%Y-%m-%d %H:%M"),
                    "pair": d.symbol,
                    "type": "Buy" if d.type == 0 else "Sell",
                    "lots": d.volume,
                    "open": d.price,  # Approximate
                    "close": d.price, # Deal execution price
                    "status": "win" if d.profit >= 0 else "loss",
                    "pl": d.profit
                })
                
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
        
        stats = {
            "win_rate": round(win_rate, 1),
            "total_trades": total_trades,
            "profit_factor": round(profit_factor, 2)
        }
        
        return {"trades": trades[:50], "stats": stats}
        
    data = await asyncio.to_thread(_fetch_hist)
    return data
