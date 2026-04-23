import os
import re
import click
from abc import ABC, abstractmethod
from typing import List, Optional, Type
from src.utils.logger import logger

class IaCDetector(ABC):
    """Abstract base class for IaC platform detectors."""
    
    @abstractmethod
    def get_name(self) -> str:
        """Returns the name of the IaC platform."""
        pass

    @abstractmethod
    def detect(self, directory: str) -> bool:
        """
        Detects if the IaC platform is present in the given directory.
        Should use both file signatures and content analysis (regex).
        """
        pass

    def _file_contains_regex(self, filepath: str, pattern: str) -> bool:
        """Helper to check if a file contains a specific regex pattern."""
        if not os.path.isfile(filepath):
            return False
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return bool(re.search(pattern, content, re.MULTILINE))
        except Exception:
            return False

class TerraformDetector(IaCDetector):
    def get_name(self) -> str:
        return "terraform"

    def detect(self, directory: str) -> bool:
        tf_files = [f for f in os.listdir(directory) if f.endswith('.tf')]
        if not tf_files:
            return False
        
        # Regex to look for HCL resource or provider blocks
        pattern = r'^\s*(resource|provider|variable|module|terraform|data)\s+"?[a-zA-Z0-9_-]+"?'
        for f in tf_files:
            if self._file_contains_regex(os.path.join(directory, f), pattern):
                return True
        return False

class OpenTofuDetector(IaCDetector):
    def get_name(self) -> str:
        return "opentofu"

    def detect(self, directory: str) -> bool:
        # OpenTofu uses .tf but can also use .tofu (future-proofing)
        tofu_files = [f for f in os.listdir(directory) if f.endswith('.tofu') or f.endswith('.tf')]
        if not tofu_files:
            return False
        
        # OpenTofu is highly compatible with Terraform, but we can look for .tofu files first
        if any(f.endswith('.tofu') for f in tofu_files):
            return True
            
        # If only .tf files, it's hard to distinguish from Terraform without specific metadata,
        # but for now we prioritize Terraform. This can be refined if OpenTofu adds unique markers.
        return False

class PulumiDetector(IaCDetector):
    def get_name(self) -> str:
        return "pulumi"

    def detect(self, directory: str) -> bool:
        # Pulumi.yaml is the definitive signature
        if 'Pulumi.yaml' in os.listdir(directory):
            return True
        
        # Content check in common Pulumi languages
        patterns = {
            '.py': r'import\s+pulumi',
            '.ts': r'import\s+.*\s+from\s+["\']@pulumi/pulumi["\']',
            '.js': r'require\(["\']@pulumi/pulumi["\']\)',
            '.go': r'github\.com/pulumi/pulumi/sdk'
        }
        
        for f in os.listdir(directory):
            _, ext = os.path.splitext(f)
            if ext in patterns:
                if self._file_contains_regex(os.path.join(directory, f), patterns[ext]):
                    return True
        return False

class AnsibleDetector(IaCDetector):
    def get_name(self) -> str:
        return "ansible"

    def detect(self, directory: str) -> bool:
        # Common ansible file names
        ansible_files = ['playbook.yml', 'playbook.yaml', 'site.yml', 'site.yaml', 'hosts', 'inventory']
        if any(f in os.listdir(directory) for f in ansible_files):
            # Verify content for YAML files to avoid false positives
            pattern = r'^\s*(hosts|tasks|roles|ansible\.builtin|become):\s*'
            for f in os.listdir(directory):
                if f.endswith(('.yml', '.yaml')) and self._file_contains_regex(os.path.join(directory, f), pattern):
                    return True
        return False

class PlatformDetectionEngine:
    """Orchestrates the detection of IaC platforms across directory levels."""
    
    def __init__(self,max_depth: int = 3):
        self.detectors: List[IaCDetector] = [
            TerraformDetector(),
            OpenTofuDetector(),
            PulumiDetector(),
            AnsibleDetector()
        ]

        self.max_depth = max_depth

    def detect(self, root_dir: str) -> List[tuple[str, str]]:
        """
        Detects all IaC platforms and their directories.
        Returns a list of tuples [(platform_name, absolute_directory_path), ...].
        """
        root_dir = os.path.abspath(root_dir)
        detected_projects = []
        
        # 1. Collect all matches recursively
        for root, dirs, files in os.walk(root_dir):
            # Calculate current depth relative to root_dir
            rel_path = os.path.relpath(root, root_dir)
            depth = 0 if rel_path == '.' else len(rel_path.split(os.sep))
            
            if depth <= self.max_depth:
                for detector in self.detectors:
                    if detector.detect(root):
                        logger.info(f"Found {detector.get_name()} in: {root}")
                        detected_projects.append((detector.get_name(), root))
                        # Prevent double-counting the same directory with different detectors 
                        # (e.g. Terraform and OpenTofu might both match)
                        break 
        
        return detected_projects

    def select_projects(self, root_dir: str, detected_projects: List[tuple[str, str]], selected_paths: Optional[List[str]] = None) -> List[tuple[str, str]]:
        """
        Handles the selection of projects. If multiple, prompts the user.
        If selected_paths is provided, filters the detected_projects by those paths.
        """
        root_dir = os.path.abspath(root_dir)

        # If user pre-selected paths via config/args
        if selected_paths:
            final_selection = []
            detected_rel_paths = []
            for platform, path in detected_projects:
                abs_path = os.path.abspath(path)
                rel_path = os.path.normpath(os.path.relpath(path, root_dir))
                detected_rel_paths.append(rel_path)
                
                # Check if any selected path matches this project
                for sp in selected_paths:
                    # If relative, join with root_dir; if absolute, use as is
                    sp_abs = os.path.abspath(os.path.join(root_dir, sp)) if not os.path.isabs(sp) else os.path.abspath(sp)
                    if abs_path == sp_abs:
                        final_selection.append((platform, path))
                        break
            
            if final_selection:
                logger.info(f"Using pre-selected projects: {click.style(', '.join(selected_paths), fg='bright_blue')}")
                return final_selection
            else:
                logger.warning("None of the pre-selected projects were detected.")
                if len(detected_rel_paths) > 0:
                    logger.warning(f"Detected projects were at: {click.style(', '.join(detected_rel_paths), fg='cyan')}")
                logger.info("Falling back to interactive mode.")

        if not detected_projects:
            logger.warning(f"No supported IaC platform detected in {root_dir} (up to {self.max_depth} levels deep).")
            click.echo("")
            
            if click.confirm(click.style("Would you like to manually specify the IaC project directory?", fg='cyan'), default=True):
                manual_dir = click.prompt(click.style("Enter the absolute path to the IaC project", fg='bright_blue')).strip()
                if os.path.isdir(manual_dir):
                    # Try to detect platform in the manual dir
                    for detector in self.detectors:
                        if detector.detect(manual_dir):
                            return [(detector.get_name(), manual_dir)]
                    
                    platforms = [d.get_name() for d in self.detectors]
                    platform_choice = click.prompt(
                        click.style(f"Could not auto-detect platform in {manual_dir}. Please choose one", fg='yellow'),
                        type=click.Choice(platforms + ['other'])
                    )
                    if platform_choice != 'other':
                        return [(platform_choice, manual_dir)]
            return []

        if len(detected_projects) == 1:
            return detected_projects

        # Multiple projects found, prompt for selection
        import inquirer
        from inquirer.themes import GreenPassion
        
        
        logger.info("Multiple IaC projects detected. Please select the ones you want to monitor:")
        click.echo("")
        click.echo("")

        choices = []
        for platform, path in detected_projects:
            rel_path = os.path.relpath(path, root_dir)
            # Format: relative_path [platform]
            label = f"{rel_path:<40} [{platform.upper()}]"
            choices.append((label, (platform, path)))

        questions = [
            inquirer.Checkbox(
                'projects',
                message="Select projects to monitor (Space to select, Enter to confirm)",
                choices=choices,
                carousel=True
            ),
        ]

        import sys
        answers = inquirer.prompt(questions, theme=GreenPassion())
        
        if answers is None:
            click.echo("\n")
            logger.info("Aborted by user.")
            sys.exit(0)
            
        selected = answers.get('projects') if answers else []

        return selected
