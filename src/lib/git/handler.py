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

    def authenticate_manually(self, url: str, pat: Optional[str] = None):
        if not pat:
            logger.info("Authentication required for private repository.")
            pat = click.prompt(
                click.style("? Enter Personal Access Token (PAT)", fg='bright_blue', bold=True),
                hide_input=True
            ).strip()
            if not pat:
                logger.error("PAT cannot be empty.")
                return False
        
        # Inject PAT into URL
        auth_url = url.replace("https://", f"https://oauth2:{pat}@")
        
        try:
            subprocess.run(
                ["git", "ls-remote", auth_url],
                check=True, capture_output=True, text=True
            )
            logger.info(f"{click.style('✔', fg='green')} Authentication successful!")
            return pat
        except subprocess.CalledProcessError:
            logger.error("Invalid PAT or access denied.")
            return False

    def clone(self, url: str, dest_dir: str, pat: str = None) -> bool:
        """Clones a repository to the specified destination."""
        if os.path.exists(dest_dir) and os.listdir(dest_dir):
            logger.warning(f"Destination directory {click.style(dest_dir, fg='bright_cyan')} already exists and is not empty.")
            new_dest = click.prompt(
                click.style("? Please enter a new destination directory", fg='bright_blue', bold=True),
                default=f"{dest_dir}_new"
            ).strip()
            return self.clone(url, new_dest, pat)

        if pat:
            url = url.replace("https://", f"https://oauth2:{pat}@")

        try:
            click.echo("")
            logger.info(f"Cloning repository: {click.style(url.split('@')[-1] if '@' in url else url, fg='bright_cyan')}...")
            Repo.clone_from(url, dest_dir)
            logger.info(f"{click.style('✔', fg='green')} Successfully cloned to {click.style(dest_dir, fg='bright_cyan')}")
            click.echo("")
            return True
        except Exception as e:
            logger.error(f"An error occurred while cloning: {e}")
            return False
