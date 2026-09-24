import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.core.logging import get_logger
from app.models.enums import ChallengeResult, ConsistencyType, DrawdownType
from app.services.risk_engine import RiskEngine, Trade

log = get_logger(__name__)


@dataclass
class ConsistencyRule:
    rule_type: ConsistencyType
    threshold_pct: float
    calculation_base: str = "total_profit"


@dataclass
class ChallengePhase:
    name: str
    profit_target_pct: float
    min_trading_days: int
    max_calendar_days: int | None = None


@dataclass
class PropFirmProfile:
    name: str
    account_size: float
    max_overall_drawdown_pct: float
    drawdown_type: DrawdownType
    max_daily_loss_pct: float
    daily_loss_includes_floating: bool
    daily_reset_timezone: str
    phases: list[ChallengePhase] = field(default_factory=list)
    consistency_rules: list[ConsistencyRule] = field(default_factory=list)


class PropFirmSimulator:
    """Evaluates a trade history against a PropFirmProfile."""

    @classmethod
    def load_profiles_from_dir(cls, directory: Path) -> dict[str, PropFirmProfile]:
        """Load all .toml profiles from a directory."""
        profiles = {}
        if not directory.exists():
            return profiles

        for toml_file in directory.glob("*.toml"):
            if toml_file.name.startswith("_"):
                continue  # Skip templates
            try:
                with open(toml_file, "rb") as f:
                    data = tomllib.load(f)

                profile_data = data.get("profile", {})
                rules_data = data.get("rules", {})
                phases_data = data.get("phases", [])
                consistency_data = data.get("consistency_rules", [])

                phases = [
                    ChallengePhase(
                        name=p.get("name", "Phase"),
                        profit_target_pct=float(p.get("profit_target_pct", 0)),
                        min_trading_days=int(p.get("min_trading_days", 0)),
                        max_calendar_days=int(p.get("max_calendar_days"))
                        if p.get("max_calendar_days")
                        else None,
                    )
                    for p in phases_data
                ]

                consistency = [
                    ConsistencyRule(
                        rule_type=ConsistencyType(c.get("rule_type")),
                        threshold_pct=float(c.get("threshold_pct", 0)),
                        calculation_base=c.get("calculation_base", "total_profit"),
                    )
                    for c in consistency_data
                ]

                # We pick the first account size as default, or allow dynamic selection later
                account_sizes = profile_data.get("account_sizes", [100000])
                account_size = float(account_sizes[0])

                profile = PropFirmProfile(
                    name=profile_data.get("name", "Unknown Profile"),
                    account_size=account_size,
                    max_overall_drawdown_pct=float(rules_data.get("max_overall_drawdown_pct", 0.1)),
                    drawdown_type=DrawdownType(rules_data.get("drawdown_type", "static")),
                    max_daily_loss_pct=float(rules_data.get("max_daily_loss_pct", 0.05)),
                    daily_loss_includes_floating=bool(
                        rules_data.get("daily_loss_includes_floating", True)
                    ),
                    daily_reset_timezone=rules_data.get("daily_reset_timezone", "UTC"),
                    phases=phases,
                    consistency_rules=consistency,
                )
                profiles[toml_file.stem] = profile
            except Exception as e:
                log.error("Failed to load prop firm profile", file=toml_file.name, error=str(e))

        return profiles

    @classmethod
    def evaluate(
        cls,
        profile: PropFirmProfile,
        trades: list[Trade],
        initial_balance: float,
        equity_curve: np.ndarray,
    ) -> dict:
        """
        Evaluate trades against prop firm rules.
        """
        if not trades:
            return cls._result_payload(ChallengeResult.IN_PROGRESS, "No trades taken yet")

        current_balance = initial_balance + sum(t.pnl for t in trades)

        # 1. Overall Drawdown Check
        if profile.drawdown_type == DrawdownType.TRAILING:
            dd = RiskEngine.drawdown_trailing(equity_curve, initial_balance)
        else:
            # Static DD relative to initial balance
            # For strict static DD: equity drops below initial_balance * (1 - max_overall_drawdown_pct)
            # Find min equity
            min_eq = min(equity_curve) if len(equity_curve) > 0 else initial_balance
            max_drop = initial_balance - min_eq
            dd_pct = max_drop / initial_balance
            from app.services.risk_engine import DrawdownResult

            dd = DrawdownResult(max_drawdown_abs=max_drop, max_drawdown_pct=dd_pct)

        if dd.max_drawdown_pct > profile.max_overall_drawdown_pct:
            return cls._result_payload(
                ChallengeResult.FAILED,
                f"Overall Drawdown breach: {dd.max_drawdown_pct:.2%} > {profile.max_overall_drawdown_pct:.2%}",
            )

        # 2. Daily Loss Check
        daily_losses = RiskEngine.daily_loss(
            trades,
            initial_balance,
            profile.daily_reset_timezone,
            profile.daily_loss_includes_floating,
        )
        max_daily_loss_pct = max((dl.max_loss_pct for dl in daily_losses), default=0.0)

        if max_daily_loss_pct > profile.max_daily_loss_pct:
            return cls._result_payload(
                ChallengeResult.FAILED,
                f"Daily Loss breach: {max_daily_loss_pct:.2%} > {profile.max_daily_loss_pct:.2%}",
            )

        # 3. Phase / Profit Target Check
        # For simplicity, we evaluate against Phase 1 (index 0) if phases exist
        if profile.phases:
            phase = profile.phases[0]
            profit_target = initial_balance * phase.profit_target_pct
            current_profit = current_balance - initial_balance

            # Trading days
            daily_pnl = RiskEngine.daily_pnl(trades, profile.daily_reset_timezone)
            trading_days = len(daily_pnl)

            if trading_days < phase.min_trading_days:
                return cls._result_payload(
                    ChallengeResult.IN_PROGRESS,
                    f"Minimum trading days not met ({trading_days}/{phase.min_trading_days})",
                )

            if current_profit < profit_target:
                return cls._result_payload(
                    ChallengeResult.IN_PROGRESS,
                    f"Profit target not met ({current_profit}/{profit_target})",
                )

        # 4. Consistency Rules Check
        if profile.consistency_rules:
            for rule in profile.consistency_rules:
                if rule.rule_type == ConsistencyType.MAX_DAY_SHARE:
                    daily_pnl = RiskEngine.daily_pnl(trades, profile.daily_reset_timezone)
                    cons_res = RiskEngine.consistency_score(trades, daily_pnl, rule.threshold_pct)
                    if not cons_res.passed:
                        return cls._result_payload(
                            ChallengeResult.FAILED,
                            f"Consistency breach: Max day share {cons_res.max_day_share:.2%} > {rule.threshold_pct:.2%}",
                        )

        return cls._result_payload(ChallengeResult.PASSED, "All requirements met")

    @staticmethod
    def _result_payload(status: ChallengeResult, detail: str) -> dict:
        return {"status": status.value, "detail": detail}
