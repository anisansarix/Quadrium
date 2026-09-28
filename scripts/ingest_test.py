import datetime
from pathlib import Path

from app.core.decision_pipeline import DecisionPipeline
from app.data.catalog import DatasetCatalog
from app.data.datasets import DatasetManager
from app.data.downloader import MT5Downloader
from app.data.providers.mt5 import MT5Provider
from app.data.providers.mt5_client import RealMT5Client
from app.domain.models import Quote, RiskPolicy, RunMetadata
from app.evaluation.backtest import BacktestRunner
from app.risk.engine import RiskEngine
from app.simulator.engine import SimulatorEngine
from app.strategies.baseline import SMATrend


def ingest_and_backtest():
    base_dir = Path("data")
    manager = DatasetManager(base_dir)
    catalog = DatasetCatalog(base_dir / "catalog.duckdb")
    
    print("Connecting to MT5...")
    client = RealMT5Client()
    provider = MT5Provider(client=client)
    provider.connect()
    
    downloader = MT5Downloader(provider, manager)
    
    end = datetime.datetime.now(datetime.UTC)
    start = end - datetime.timedelta(days=7) # Fetch 1 week of data
    
    symbol = "EURUSD"
    spec = provider.get_instrument_spec(symbol)
    
    for timeframe in ["M1", "M5"]:
        print(f"Downloading {timeframe} for {symbol}...")
        dataset_id, report = downloader.download_bars(symbol, timeframe, start, end)
        
        manifest_path = manager.manifest_dir / f"{dataset_id}.json"
        import json
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f)
            from app.domain.models import DatasetManifest
            manifest = DatasetManifest(**manifest_data)
            
        catalog.register_dataset(manifest, manager.canonical_dir / f"{dataset_id}.parquet")
        
        print(f"Dataset {dataset_id} created with Hash: {manifest.dataset_hash}")
        print(f"Gaps: {report.model_dump_json(indent=2)}")
        
        # Load and run backtest
        print("Running Simulator against dataset...")
        df = manager.load_canonical(dataset_id)
        
        quotes = []
        for _, row in df.iterrows():
            quotes.append(Quote(
                timestamp=row['timestamp'],
                symbol=symbol,
                bid=row['close'],
                ask=row['close'] + row.get('spread', 0)*spec.point
            ))
            
        sim = SimulatorEngine(initial_balance=10000.0)
        risk_engine = RiskEngine()
        pipeline = DecisionPipeline(risk_engine)
        
        policy = RiskPolicy(
            id="test-pol", version="1.0", max_daily_loss_pct=0.05, max_drawdown_pct=0.10,
            max_trade_risk_pct=0.01, max_open_risk_pct=0.05, max_gross_exposure=1000000.0,
            max_net_exposure=50000.0, max_position_count=5, max_spread_pts=50,
            require_sl=False, session_constraints={}, leverage_limit=30.0
        )
        
        strategy = SMATrend(symbol=symbol, fast_period=20, slow_period=50, target_weight=1.0)
        runner = BacktestRunner(sim, pipeline, policy, strategy)
        
        metadata = RunMetadata(
            dataset_hash=manifest.dataset_hash,
            simulator_version="1.0",
            environment_version="1.0"
        )
        
        res = runner.run(quotes, spec, metadata)
        print(f"Backtest complete for {timeframe}. Executions: {len(res.executions)}, Final Equity: {res.equity_curve[-1].equity}")
        print("-" * 50)
        
    provider.disconnect()

if __name__ == "__main__":
    ingest_and_backtest()
