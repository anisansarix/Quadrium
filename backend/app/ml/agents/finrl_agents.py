import torch
from stable_baselines3 import PPO, SAC, A2C, TD3, DDPG
from stable_baselines3.common.base_class import BaseAlgorithm
from gymnasium import Env

from app.core.exceptions import TrainingError
from app.core.logging import get_logger

log = get_logger(__name__)

class AgentFactory:
    """
    Factory for instantiating and managing Stable-Baselines3 (FinRL) agents.
    Handles device configuration and architecture choices.
    """
    
    SUPPORTED_AGENTS = ["ppo", "sac", "a2c", "td3", "ddpg"]
    
    @classmethod
    def create_agent(
        cls, 
        agent_type: str, 
        env: Env, 
        hyperparams: dict | None = None
    ) -> BaseAlgorithm:
        """Create a new agent instance."""
        agent_type = agent_type.lower()
        if agent_type not in cls.SUPPORTED_AGENTS:
            raise TrainingError(f"Unsupported agent type: {agent_type}")
            
        hyperparams = hyperparams or {}
        
        # Configure device (respecting VRAM limits for RTX 3050 Laptop)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Default policy kwargs for financial time series
        policy_kwargs = hyperparams.pop("policy_kwargs", {
            "net_arch": dict(pi=[64, 64], vf=[64, 64])
        })
        
        # Merge defaults tailored for low VRAM
        if agent_type == "ppo":
            defaults = {
                "batch_size": 64, # Small batch for 4GB VRAM
                "n_steps": 2048,
                "learning_rate": 3e-4,
                "device": device,
                "policy_kwargs": policy_kwargs,
            }
            defaults.update(hyperparams)
            return PPO("MlpPolicy", env, **defaults)
            
        elif agent_type == "sac":
            defaults = {
                "batch_size": 64,
                "learning_rate": 3e-4,
                "buffer_size": 100000, # Constrained buffer
                "device": device,
                "policy_kwargs": policy_kwargs,
            }
            defaults.update(hyperparams)
            return SAC("MlpPolicy", env, **defaults)
            
        elif agent_type == "a2c":
            defaults = {
                "learning_rate": 7e-4,
                "device": device,
                "policy_kwargs": policy_kwargs,
            }
            defaults.update(hyperparams)
            return A2C("MlpPolicy", env, **defaults)
            
        elif agent_type == "td3":
            defaults = {
                "batch_size": 64,
                "learning_rate": 1e-3,
                "buffer_size": 100000,
                "device": device,
                "policy_kwargs": policy_kwargs,
            }
            defaults.update(hyperparams)
            return TD3("MlpPolicy", env, **defaults)
            
        elif agent_type == "ddpg":
            defaults = {
                "batch_size": 64,
                "learning_rate": 1e-3,
                "buffer_size": 100000,
                "device": device,
                "policy_kwargs": policy_kwargs,
            }
            defaults.update(hyperparams)
            return DDPG("MlpPolicy", env, **defaults)
            
        raise TrainingError("Unexpected agent type")

    @classmethod
    def load_agent(cls, agent_type: str, path: str, env: Env | None = None) -> BaseAlgorithm:
        """Load a saved agent from disk."""
        agent_type = agent_type.lower()
        if agent_type == "ppo":
            return PPO.load(path, env=env)
        elif agent_type == "sac":
            return SAC.load(path, env=env)
        elif agent_type == "a2c":
            return A2C.load(path, env=env)
        elif agent_type == "td3":
            return TD3.load(path, env=env)
        elif agent_type == "ddpg":
            return DDPG.load(path, env=env)
            
        raise AppError(f"Unsupported agent type: {agent_type}")
