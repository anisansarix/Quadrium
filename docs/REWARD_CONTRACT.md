# Reward Contract (Phase 3)

## Default Reward Semantics
The default RL environment step reward emits the exact unscaled incremental marked-to-market equity return generated over the preceding discrete action boundary.

Formula:
eward = (current_equity - previous_equity) / previous_equity (if previous_equity > 0, else 0)

This captures explicitly realized and unrealized variations identically without introducing synthetic reshaping, ensuring the policy optimizes identical contours to standard quantitative baseline tracking.
