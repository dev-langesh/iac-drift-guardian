import os
import yaml
import json
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class ConfigModel(BaseModel):
    repo_url: Optional[str] = Field(None, alias="repoUrl")
    iac_type: Optional[str] = Field(None, alias="iacType")
    pat: Optional[str] = None
    output_dir: str = Field("cloned_repos", alias="outputDir")

    class Config:
        populate_by_name = True

def load_config(config_path: str) -> Dict[str, Any]:
    """Loads configuration from a YAML or JSON file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    _, ext = os.path.splitext(config_path)
    with open(config_path, 'r') as f:
        if ext.lower() in ['.yaml', '.yml']:
            data = yaml.safe_load(f)
        elif ext.lower() == '.json':
            data = json.load(f)
        else:
            raise ValueError(f"Unsupported config file format: {ext}")

    # Validate with Pydantic
    config = ConfigModel(**data)
    return config.model_dump()

def get_default_config_path() -> Optional[str]:
    """Checks for default config files in the current directory."""
    for filename in ["config.yml", "config.yaml", "config.json"]:
        if os.path.exists(filename):
            return filename
    return None
