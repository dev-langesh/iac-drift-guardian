import os
import shutil
import subprocess
import click
import re
from typing import Optional, Tuple
from git import Repo, GitCommandError
from src.utils.logger import logger

class GitHandler:
    def __init__(self, pat: Optional[str] = None):
        self.pat = pat

    @staticmethod
    def is_git_installed() -> bool:
        """Checks if git is installed on the system."""
        try:
            subprocess.run(["git", "--version"], check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def is_valid_git_url(self, url: str) -> bool:
        """Heuristic check if string is a git URL."""
        if not url:
            return False
        # Matches https://, git@, etc.
        git_url_pattern = r'^(https?|git|ssh|rsync)://|git@|.*\.git$'
        return bool(re.match(git_url_pattern, url))

    def verify_access(self, repo_url: str, pat: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Checks if the user has access to the repository using git ls-remote."""
        url_to_check = self._prepare_url(repo_url, pat)
        try:
            # We use git ls-remote to check connectivity and auth without cloning
            subprocess.run(["git", "ls-remote", url_to_check], check=True, capture_output=True)
            return True, pat
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode()
            
            # 1. Explicit Access Denied / Auth Failure
            if any(term in error_msg for term in ["Authentication failed", "Permission denied", "could not read Password"]):
                if not pat:
                    logger.warning("Access denied to the repository. Authentication required.")
                    prompt_msg = click.style("Please enter your Personal Access Token (PAT)", fg='yellow')
                    new_pat = click.prompt(prompt_msg, hide_input=True).strip()
                    if new_pat:
                        return self.verify_access(repo_url, new_pat)
                else:
                    logger.error("The provided PAT failed authentication.")
            
            # 2. Repository Not Found (Could be a typo OR a private repo)
            elif "not found" in error_msg.lower() or "repository not found" in error_msg.lower():
                if not pat:
                    logger.warning(f"Repository not found at: {repo_url}")
                    if click.confirm(click.style("Is this a private repository?", fg='cyan'), default=False):
                        prompt_msg = click.style("Please enter your Personal Access Token (PAT)", fg='yellow')
                        new_pat = click.prompt(prompt_msg).strip()
                        if new_pat:
                            return self.verify_access(repo_url, new_pat)
                else:
                    logger.error(f"Repository still not found even with PAT. Please check the URL: {repo_url}")
            
            # 3. Other errors
            else:
                logger.error(f"Failed to verify repository: {error_msg.strip()}")
            
            return False, pat

    def _prepare_url(self, repo_url: str, pat: Optional[str] = None) -> str:
        """Injects PAT into the repo URL if provided."""
        if not pat:
            return repo_url
        if repo_url.startswith("https://") and "@" not in repo_url:
            return repo_url.replace("https://", f"https://{pat}@")
        return repo_url

    def clone(self, repo_url: str, dest_dir: str, pat: Optional[str] = None) -> Optional[Repo]:
        """Clones a git repository to the destination directory."""
        if not self.is_git_installed():
            logger.error("Git is not installed on this system. Please install git to proceed.")
            return None

        while os.path.exists(dest_dir) and os.listdir(dest_dir):
            logger.warning(f"Destination directory {dest_dir} already exists and is not empty.")
            prompt_msg = click.style(f"Please enter a new destination directory", fg='cyan')
            dest_dir = click.prompt(prompt_msg).strip()

        try:
            url_to_clone = self._prepare_url(repo_url, pat)
            logger.info(f"Cloning repository: {repo_url}")
            repo = Repo.clone_from(url_to_clone, dest_dir)
            logger.info(f"Successfully cloned to {dest_dir}")
            return repo
        except GitCommandError as e:
            logger.error(f"An error occurred while cloning: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during cloning: {e}")
            return None
