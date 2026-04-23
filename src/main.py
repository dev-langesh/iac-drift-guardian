import os
import sys
import click

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import logger, print_banner
from src.config import load_config, get_default_config_path
from src.lib.git.handler import GitHandler

@click.command()
@click.option('--repo-url', '-r', help='URL of the Git repository or absolute path to local source.')
@click.option('--config', '-c', help='Path to the configuration file (YAML or JSON).')
@click.option('--pat', '-p', help='Personal Access Token for Git authentication.')
@click.option('--output-dir', '-o', help='Directory to clone the repository into.')
def main(repo_url, config, pat, output_dir):
    """IaC Drift Guardian - Detect drift in your Infrastructure as Code."""
    
    print_banner()
    logger.info("Starting IaC Drift Guardian...")

    config_data = {}
    
    # 1. Load from config file if provided or default exists
    config_path = config or get_default_config_path()
    if config_path:
        try:
            logger.info(f"Loading configuration from {config_path}")
            config_data = load_config(config_path)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            if config:
                return

    # 2. Merge initial values
    repo_url = repo_url or config_data.get('repo_url')
    pat = pat or config_data.get('pat')
    output_dir = output_dir or config_data.get('output_dir') or 'cloned_repos'

    git_handler = GitHandler(pat=pat)
    final_source_path = None

    # 3. Validation Loop
    while not final_source_path:
        if not repo_url:
            prompt_msg = click.style("Please enter the Git repository URL or absolute local path", fg='bright_blue', bold=True)
            repo_url = click.prompt(prompt_msg).strip()

        # Case A: Absolute Local Path
        if os.path.isabs(repo_url):
            if os.path.isdir(repo_url):
                logger.info(f"Using local source directory: {repo_url}")
                final_source_path = repo_url
            else:
                logger.error(f"The provided path is not a directory: {repo_url}")
                repo_url = None # Force retry
                continue

        # Case B: Git Repository URL
        elif git_handler.is_valid_git_url(repo_url):
            success, validated_pat = git_handler.verify_access(repo_url, pat)
            if success:
                pat = validated_pat # Update PAT if prompted during verification
                
                # Generate a destination path
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                dest_path = os.path.join(output_dir, repo_name)
                
                repo = git_handler.clone(repo_url, dest_path, pat)
                if repo:
                    final_source_path = dest_path
                else:
                    repo_url = None # Force retry
            else:
                logger.error(f"Could not access the repository: {repo_url}")
                repo_url = None # Force retry
        
        else:
            logger.error(f"Invalid input. Please provide a valid Git URL or an absolute local path: {repo_url}")
            repo_url = None # Force retry

    if final_source_path:
        logger.info(f"Source code ready at: {final_source_path}")
        
        # 4. IaC Platform Detection 
        from src.lib.iac.detector import PlatformDetectionEngine
        detection_engine = PlatformDetectionEngine()
        
        detected_list = detection_engine.detect(final_source_path)
        selected_projects = detection_engine.select_projects(final_source_path, detected_list)
        
        if selected_projects:
            for platform, project_dir in selected_projects:
                logger.info(f"Ready to monitor {click.style(platform.upper(), fg='green', bold=True)} project at {click.style(project_dir, fg='bright_cyan')}")
        else:
            logger.error("No projects selected. Exiting.")
            return

        click.echo("") 
        logger.info("Task completed successfully!")
    else:
        logger.error("Task failed.")

if __name__ == "__main__":
    main()
