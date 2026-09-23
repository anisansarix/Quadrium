"""GPU/CUDA verification script for Quadrium.

Run this script to confirm your GPU is properly configured for ML training.
Usage: python scripts/verify_gpu.py
"""

from __future__ import annotations

import platform
import sys


def main() -> None:
    print("=" * 60)
    print("Quadrium GPU/CUDA Verification")
    print("=" * 60)
    print()

    # System info
    print(f"Python:    {sys.version}")
    print(f"Platform:  {platform.platform()}")
    print(f"Processor: {platform.processor()}")
    print()

    # PyTorch
    try:
        import torch

        print(f"PyTorch:   {torch.__version__}")
        print(f"CUDA available:  {torch.cuda.is_available()}")

        if torch.cuda.is_available():
            print(f"CUDA version:    {torch.version.cuda}")
            print(f"cuDNN version:   {torch.backends.cudnn.version()}")
            print(f"Device count:    {torch.cuda.device_count()}")
            print()

            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                total_mem = props.total_memory / (1024 ** 2)
                print(f"--- GPU {i}: {props.name} ---")
                print(f"  Compute capability: {props.major}.{props.minor}")
                print(f"  Total memory:       {total_mem:.0f} MB")
                print(f"  Multi-processors:   {props.multi_processor_count}")
                print()

            # Quick tensor test
            print("Running GPU tensor test...")
            x = torch.randn(1000, 1000, device="cuda")
            y = torch.randn(1000, 1000, device="cuda")
            z = torch.mm(x, y)
            print(f"  Matrix multiply (1000x1000): OK")
            print(f"  Result shape: {z.shape}")
            print(f"  GPU memory allocated: {torch.cuda.memory_allocated() / (1024**2):.1f} MB")
            print(f"  GPU memory cached:    {torch.cuda.memory_reserved() / (1024**2):.1f} MB")
            del x, y, z
            torch.cuda.empty_cache()
            print()

            # Mixed precision test
            print("Testing mixed precision (AMP)...")
            with torch.amp.autocast("cuda"):
                a = torch.randn(1000, 1000, device="cuda")
                b = torch.randn(1000, 1000, device="cuda")
                c = torch.mm(a, b)
                print(f"  AMP matrix multiply: OK (dtype={c.dtype})")
            del a, b, c
            torch.cuda.empty_cache()
            print()

            print("✓ GPU is ready for Quadrium ML training.")
        else:
            print()
            print("⚠ CUDA not available. Training will use CPU (slower).")
            print("  To enable GPU:")
            print("  1. Install NVIDIA drivers")
            print("  2. Install PyTorch with CUDA:")
            print("     pip install torch --index-url https://download.pytorch.org/whl/cu121")
    except ImportError:
        print("✗ PyTorch not installed.")
        print("  Install: pip install torch --index-url https://download.pytorch.org/whl/cu121")

    print()

    # System memory
    try:
        import psutil

        vm = psutil.virtual_memory()
        print(f"System RAM:  {vm.total / (1024**3):.1f} GB total, {vm.available / (1024**3):.1f} GB available")
    except ImportError:
        print("(psutil not installed — skipping RAM check)")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
