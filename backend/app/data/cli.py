import argparse
import datetime
from pathlib import Path

from app.data.catalog import DatasetCatalog
from app.data.datasets import DatasetManager
from app.data.downloader import MT5Downloader
from app.data.providers.mt5 import MT5Provider
from app.data.providers.mt5_client import RealMT5Client
from app.data.validation import validate_dataframe


def main():
    parser = argparse.ArgumentParser(prog="app.data.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    p_inst = subparsers.add_parser("instrument")
    p_inst.add_argument("symbol")
    
    p_bars = subparsers.add_parser("bars")
    p_bars.add_argument("symbol")
    p_bars.add_argument("timeframe")
    p_bars.add_argument("start")
    p_bars.add_argument("end")
    
    p_ticks = subparsers.add_parser("ticks")
    p_ticks.add_argument("symbol")
    p_ticks.add_argument("start")
    p_ticks.add_argument("end")
    
    p_val = subparsers.add_parser("validate")
    p_val.add_argument("dataset")
    
    subparsers.add_parser("catalog")
    
    args = parser.parse_args()
    
    base_dir = Path("data")
    manager = DatasetManager(base_dir)
    catalog = DatasetCatalog(base_dir / "catalog.duckdb")
    
    # We only connect to MT5 for fetch commands
    if args.command in ("instrument", "bars", "ticks"):
        provider = MT5Provider(client=RealMT5Client())
        provider.connect()
        
    if args.command == "instrument":
        spec = provider.get_instrument_spec(args.symbol)
        print(spec.model_dump_json(indent=2))
        
    elif args.command == "bars":
        start = datetime.datetime.fromisoformat(args.start)
        end = datetime.datetime.fromisoformat(args.end)
        downloader = MT5Downloader(provider, manager)
        dataset_id, report = downloader.download_bars(args.symbol, args.timeframe, start, end)
        
        manifest_path = manager.manifest_dir / f"{dataset_id}.json"
        import json
        with open(manifest_path, "r") as f:
            manifest_data = json.load(f)
            from app.domain.models import DatasetManifest
            manifest = DatasetManifest(**manifest_data)
            
        catalog.register_dataset(manifest, manager.canonical_dir / f"{dataset_id}.parquet")
        
        print(f"Downloaded dataset: {dataset_id}")
        print(report.model_dump_json(indent=2))
        
    elif args.command == "ticks":
        start = datetime.datetime.fromisoformat(args.start)
        end = datetime.datetime.fromisoformat(args.end)
        df = provider.fetch_ticks(args.symbol, start, end)
        manager.save_raw(df, "mt5", args.symbol, "ticks")
        print(f"Downloaded {len(df)} ticks.")
        
    elif args.command == "validate":
        df = manager.load_canonical(args.dataset)
        validate_dataframe(df)
        print("Validation passed.")
        
    elif args.command == "catalog":
        datasets = catalog.query_datasets()
        for d in datasets:
            print(d)

if __name__ == "__main__":
    main()
