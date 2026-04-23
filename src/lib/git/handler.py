import os
import shutil
import subprocess
import click
import sys
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

    def _is_same_remote(self, repo: Repo, url: str) -> bool:
        """Checks if the repository's remote URL matches the target URL."""
        try:
            remote_url = repo.remotes.origin.url
            # Strip auth from both for comparison
            target_clean = re.sub(r'https://[^@]+@', 'https://', url)
            remote_clean = re.sub(r'https://[^@]+@', 'https://', remote_url)
            return target_clean == remote_clean or remote_url == url
        except (AttributeError, IndexError):
            return False

    def clone(self, url: str, dest_dir: str, pat: str = None, collision_action: str = None) -> str:
        """
        Clones a repository or updates it if it already exists.
        Returns the final destination directory path or False on failure.
        """
        if os.path.exists(dest_dir) and os.listdir(dest_dir):
            logger.info(f"Directory {click.style(dest_dir, fg='bright_cyan')} already exists.\n\n")
            # 1. Check if it's a matching git repo
            is_git_repo = False
            try:
                repo = Repo(dest_dir)
                is_git_repo = True
            except Exception:
                is_git_repo = False

            matching_repo = is_git_repo and self._is_same_remote(repo, url)

            # 2. Collision options - Use provided action or ask user
            import inquirer
            from inquirer.themes import GreenPassion
            
            action = collision_action
            if not action:
                choices = []
                if matching_repo:
                    choices.extend([
                        ("Pull latest changes from remote", "pull"),
                        ("Use existing local code", "continue"),
                    ])
                
                choices.extend([
                    ("Clone in different directory", "new"),
                    ("Override existing directory (Delete everything)", "override"),
                    ("Use a different repository URL", "cancel")
                ])
                
                questions = [
                    inquirer.List(
                        'action',
                        message=f"Directory {os.path.basename(dest_dir)} already exists. How would you like to proceed?",
                        choices=choices,
                    ),
                ]
                
                answers = inquirer.prompt(questions, theme=GreenPassion())
                
                # Handle Ctrl+C (Inquirer returns None when cancelled)
                if answers is None:
                    click.echo("\n")
                    logger.info("Aborted by user.")
                    sys.exit(0)
                    
                action = answers.get('action')
            else:
                logger.info(f"Using pre-configured collision action: {click.style(action, fg='bright_blue')}")

            if action == "pull":
                if repo.is_dirty(untracked_files=True):
                    logger.warning("Local repository has uncommitted changes. Pull might fail or cause conflicts.")
                    if not click.confirm(click.style("Do you still want to attempt a pull?", fg='yellow'), default=False):
                        return self.clone(url, dest_dir, pat) # Re-prompt
                
                try:
                    logger.info("Attempting to pull updates...")
                    repo.remotes.origin.pull()
                    logger.info(f"{click.style('✔', fg='green')} Successfully updated existing repository at {click.style(dest_dir, fg='bright_cyan')}")
                    return dest_dir
                except Exception as e:
                    logger.error(f"Failed to pull updates: {e}")
                    return self.clone(url, dest_dir, pat) # Re-prompt for other options

            elif action == "continue":
                logger.info(f"Using existing code at {click.style(dest_dir, fg='bright_cyan')}")
                return dest_dir

            elif action == "new":
                parent_dir = os.path.dirname(dest_dir)
                new_name = click.prompt(
                    click.style("? Enter new directory name", fg='bright_blue', bold=True),
                    default=f"{os.path.basename(dest_dir)}_v2"
                ).strip()
                return self.clone(url, os.path.join(parent_dir, new_name), pat)
            
            elif action == "override":
                if click.confirm(click.style(f"❗ This will PERMANENTLY DELETE {dest_dir}. Continue?", fg='red', bold=True)):
                    try:
                        shutil.rmtree(dest_dir)
                        logger.info(f"Deleted existing directory: {dest_dir}")
                    except Exception as e:
                        logger.error(f"Failed to delete directory: {e}")
                        return False
                else:
                    return self.clone(url, dest_dir, pat)
            else:
                return False

        # 3. Standard Clone
        if pat:
            clone_url = url.replace("https://", f"https://oauth2:{pat}@")
        else:
            clone_url = url

        try:
            click.echo("")
            logger.info(f"Cloning repository: {click.style(url, fg='bright_cyan')}...")
            Repo.clone_from(clone_url, dest_dir)
            logger.info(f"{click.style('✔', fg='green')} Successfully cloned to {click.style(dest_dir, fg='bright_cyan')}")
            click.echo("")
            return dest_dir
        except Exception as e:
            logger.error(f"An error occurred while cloning: {e}")
            return False
