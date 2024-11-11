"""
Conversation Configuration Module

This module handles the loading and management of conversation configuration settings
for the Podcastfy application. It uses a YAML file for conversation-specific configuration settings.
"""

import copy
from typing import Any, Dict, Optional, List
import yaml
from .config import NestedConfig, get_config_path

class ConversationConfig(NestedConfig):
	def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
		"""
		Initialize the ConversationConfig class with a dictionary configuration.

		Args:
			config_dict (Optional[Dict[str, Any]]): Configuration dictionary. If None, default config will be used.
		"""
		# Load default configuration
		default_config = self._load_default_config()
		
		if config_dict is not None:
			# Create a deep copy of the default configuration
			merged_config = copy.deepcopy(default_config)
			# Update with provided configuration
			self._deep_update(merged_config, config_dict)
		else:
			merged_config = default_config
		
		# Initialize the NestedConfig with the merged configuration
		super().__init__(merged_config)

	def _load_default_config(self) -> Dict[str, Any]:
		"""Load the default configuration from conversation_config.yaml."""
		config_path = get_config_path('conversation_config.yaml')
		if config_path:
			with open(config_path, 'r') as file:
				return yaml.safe_load(file)
		else:
			raise FileNotFoundError("conversation_config.yaml not found")

	def _deep_update(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
		"""
		Recursively update a nested dictionary.

		Args:
			target (Dict[str, Any]): The dictionary to update
			source (Dict[str, Any]): The dictionary containing updates
		"""
		for key, value in source.items():
			if isinstance(value, dict) and key in target and isinstance(target[key], dict):
				self._deep_update(target[key], value)
			else:
				target[key] = value

	def get_list(self, key: str, default: Optional[List[str]] = None) -> List[str]:
		"""
		Get a list configuration value by key, supporting nested keys with dot notation.

		Args:
			key (str): The configuration key to retrieve (e.g., 'child.list')
			default (Optional[List[str]]): The default value if the key is not found.

		Returns:
			List[str]: The list associated with the key, or the default value if not found.
		"""
		value = self.get(key, default)
		if isinstance(value, str):
			return [item.strip() for item in value.split(',')]
		return value if isinstance(value, list) else default or []

def load_conversation_config(config_dict: Optional[Dict[str, Any]] = None) -> ConversationConfig:
	"""
	Load and return a ConversationConfig instance.

	Args:
		config_dict (Optional[Dict[str, Any]]): Configuration dictionary to use. If None, default config will be used.

	Returns:
		ConversationConfig: An instance of the ConversationConfig class.
	"""
	return ConversationConfig(config_dict)
