"""
Configuration Module

This module handles the loading and management of configuration settings for the Podcastfy application.
It uses environment variables to securely store and access API keys and other sensitive information,
and a YAML file for non-sensitive configuration settings.
"""

import os
from dotenv import load_dotenv, find_dotenv 
from typing import Any, Dict, Optional
import yaml
import copy

class NestedConfig:
    """
    A class to handle nested configuration objects with proper method inheritance.
    """
    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize a nested configuration object.

        Args:
            config_dict (Dict[str, Any]): Dictionary containing the nested configuration
        """
        for key, value in config_dict.items():
            if isinstance(value, dict):
                setattr(self, key, NestedConfig(value))
            else:
                setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the NestedConfig object to a dictionary, preserving nested structure.

        Returns:
            Dict[str, Any]: A dictionary representation of the configuration
        """
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                if isinstance(value, NestedConfig):
                    result[key] = value.to_dict()
                else:
                    result[key] = value
        return result
    
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Get a configuration value by key, supporting nested keys with dot notation.

        Args:
            key (str): The configuration key to retrieve (e.g., 'child.value')
            default (Optional[Any]): The default value if the key is not found.

        Returns:
            Any: The value associated with the key, or the default value if not found.
        """
        current = self
        try:
            for part in key.split('.'):
                if isinstance(current, dict):
                    current = current[part]
                else:
                    current = getattr(current, part)
            return current
        except (AttributeError, KeyError):
            return default

    def configure(self, config: Dict[str, Any]) -> None:
        """
        Configure the settings with the provided dictionary.

        Args:
            config (Dict[str, Any]): Configuration dictionary to update the settings.
        """
        for key, value in config.items():
            if isinstance(value, dict) and hasattr(self, key) and isinstance(getattr(self, key), NestedConfig):
                getattr(self, key).configure(value)
            else:
                setattr(self, key, value)

class Config(NestedConfig):
    def __init__(self, config_file: str = 'config.yaml'):
        """
        Initialize the Config class by loading environment variables and YAML configuration.

        Args:
            config_file (str): Path to the YAML configuration file. Defaults to 'config.yaml'.
        """
        # Try to find .env file
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path)
        else:
            print("Warning: .env file not found. Using environment variables if available.")
        
        # Load API keys from environment variables
        api_keys = {
            "JINA_API_KEY": os.getenv("JINA_API_KEY", ""),
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
            "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY", "")
        }
        
        config_path = get_config_path(config_file)
        if config_path:
            with open(config_path, 'r') as file:
                config_dict = yaml.safe_load(file)
        else:
            print("Could not locate config.yaml")
            config_dict = {}
            
        # Merge API keys with config
        config_dict.update(api_keys)
        
        # Initialize NestedConfig with the merged configuration
        super().__init__(config_dict)
        
        # Create output directories if specified
        self._setup_directories()

    def _setup_directories(self):
        """Set up output directories specified in the configuration."""
        output_dirs = self.get('output_directories', {})
        if isinstance(output_dirs, dict):
            for dir_path in output_dirs.values():
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)

def get_config_path(config_file: str = 'config.yaml'):
    """
    Get the path to the config.yaml file.
    
    Returns:
        str: The path to the config.yaml file.
    """
    try:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Look for config.yaml in the config directory
        config_path = os.path.join(base_path, 'config', config_file)
        if os.path.exists(config_path):
            return config_path
        
        # If not found, look in the package root
        config_path = os.path.join(base_path, config_file)
        if os.path.exists(config_path):
            return config_path
        
        # If not found, look in the current working directory
        config_path = os.path.join(os.getcwd(), config_file)
        if os.path.exists(config_path):
            return config_path
        
        raise FileNotFoundError(f"{config_file} not found")
    
    except Exception as e:
        print(f"Error locating {config_file}: {str(e)}")
        return None

def load_config() -> Config:
    """
    Load and return a Config instance.

    Returns:
        Config: An instance of the Config class.
    """
    return Config()