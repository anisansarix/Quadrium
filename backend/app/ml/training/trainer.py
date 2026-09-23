import os
from pathlib import Path
from typing import Any

import mlflow
import torch

from stable_baselines3.common.callbacks import BaseCallback
from app.config import settings
from app.core.logging import get_logger
from app.ml.environments.forex_env import QuadriumTradingEnv
from app.ml.agents.finrl_agents import AgentFactory

log = get_logger(__name__)


class MLflowLoggingCallback(BaseCallback):
    """Callback for logging metrics to MLflow during training."""
    
    def __init__(self, verbose=0):
        super().__init__(verbose)
        self.episode_rewards = []
        
    def _on_step(self) -> bool:
        # Check if episode ended
        if "dones" in self.locals and self.locals["dones"][0]:
            info = self.locals["infos"][0]
            if "net_worth" in info:
                mlflow.log_metric("net_worth", info["net_worth"], step=self.num_timesteps)
        
        # Log training metrics
        if self.model.logger:
            for k, v in self.model.logger.name_to_value.items():
                mlflow.log_metric(k, v, step=self.num_timesteps)
                
        return True


class Trainer:
    """Orchestrates the RL training process with FinRL and MLflow."""
    
    def __init__(self, experiment_id: str, df: Any, agent_type: str = "ppo", hyperparams: dict | None = None):
        self.experiment_id = experiment_id
        self.df = df
        self.agent_type = agent_type
        self.hyperparams = hyperparams or {}
        
        # Setup MLflow
        mlflow_dir = settings.resolve_path("mlruns")
        mlflow_dir.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(f"sqlite:///{mlflow_dir}/mlflow.db")
        mlflow.set_experiment("quadrium_trading")
        
    def train(self, total_timesteps: int = 10000) -> str:
        """Run the training loop and save the model."""
        log.info("Starting training", experiment_id=self.experiment_id, agent=self.agent_type)
        
        # 1. Setup environment
        env = QuadriumTradingEnv(self.df)
        
        # 2. Setup agent
        agent = AgentFactory.create_agent(self.agent_type, env, self.hyperparams)
        
        # 3. Train with MLflow
        with mlflow.start_run(run_name=self.experiment_id) as run:
            # Log params
            mlflow.log_param("agent_type", self.agent_type)
            mlflow.log_params(self.hyperparams)
            mlflow.log_param("total_timesteps", total_timesteps)
            
            # Use mixed precision context if supported (handled by SB3 somewhat, or we can use AMP in env/models if we dig deeper)
            # For RTX 3050 4GB, PyTorch autocast is very helpful
            with torch.amp.autocast("cuda"):
                callback = MLflowLoggingCallback()
                agent.learn(total_timesteps=total_timesteps, callback=callback)
                
            # Save model
            model_dir = settings.resolve_path("models") / self.experiment_id
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = str(model_dir / "model")
            agent.save(model_path)
            
            # Log artifact
            mlflow.log_artifact(model_path + ".zip", artifact_path="models")
            
            log.info("Training completed", run_id=run.info.run_id)
            return run.info.run_id
