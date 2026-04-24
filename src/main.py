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
@click.option('--max-depth', '-d', type=int, help='Maximum depth to search for IaC projects.')
@click.option('--projects', '-s', help='Comma-separated list of relative paths to projects to monitor.')
@click.option('--collision', help='Action to take on directory collision (pull, continue, override, new).')
@click.option('--sns-arn', help='AWS SNS Topic ARN for drift notifications.')
def main(repo_url, config, pat, output_dir, max_depth, projects, collision, sns_arn):
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

    # 2. Merge values (CLI args override config file)
    repo_url = repo_url or config_data.get('repo_url')
    pat = pat or config_data.get('pat')
    output_dir = output_dir or config_data.get('output_dir') or 'cloned_repos'
    max_depth = max_depth or config_data.get('max_depth') or 3
    sns_arn = sns_arn or config_data.get('aws_sns_arn')
    
    # Handle selected projects (from CLI as string, from config as list)
    selected_projects = None
    if projects:
        selected_projects = [p.strip() for p in projects.split(',')]
    else:
        selected_projects = config_data.get('selected_projects')
        
    collision_action = collision or config_data.get('collision_action')

    git_handler = GitHandler(pat=pat)
    final_source_path = None

    # 3. Validation Loop
    while not final_source_path:
        if not repo_url:
            prompt_msg = click.style("Please enter the Git repository URL or absolute local path", fg='bright_blue', bold=True)
            repo_url = click.prompt(prompt_msg).strip()
            
        if not sns_arn:
            sns_prompt_msg = click.style("Please enter the AWS SNS Topic ARN for notifications (or press Enter to skip)", fg='bright_blue')
            sns_arn = click.prompt(sns_prompt_msg, default="", show_default=False).strip()
            if not sns_arn:
                logger.warning("No SNS ARN provided. Notifications will be disabled.")

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
                
                # Pass collision_action to clone
                repo = git_handler.clone(repo_url, dest_path, pat, collision_action=collision_action)
                if repo:
                    final_source_path = repo
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
        detection_engine = PlatformDetectionEngine(max_depth=max_depth)
        
        detected_list = detection_engine.detect(final_source_path)
        # Pass pre-selected projects to bypass prompt
        monitoring_projects = detection_engine.select_projects(final_source_path, detected_list, selected_paths=selected_projects)
        
        if monitoring_projects:
            from src.lib.docker.builder import DockerBuilder
            docker_builder = DockerBuilder(output_dir=output_dir)
            
            for platform, project_dir in monitoring_projects:
                logger.info(f"\nReady to process {click.style(platform.upper(), fg='green', bold=True)} project at {click.style(project_dir, fg='bright_cyan')}")
                
                # Build Docker Image
                image_name = docker_builder.build_image(
                    iac_tool=platform,
                    project_dir=project_dir,
                    sns_arn=sns_arn
                )
                
                if image_name:
                    logger.info(f"Docker image {click.style(image_name, fg='bright_blue')} is ready for ECR push.")
                else:
                    logger.error(f"Failed to build Docker image for {project_dir}")
        else:
            logger.error("No projects selected. Exiting.")
            return

        click.echo("") 
        logger.info("Task completed successfully!")
    else:
        logger.error("Task failed.")

if __name__ == "__main__":
    main()
