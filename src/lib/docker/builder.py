import os
import subprocess
import click
from src.utils.logger import logger

class DockerBuilder:
    """Handles the creation of tailored Docker images for specific IaC projects."""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.dockerfiles_dir = os.path.join(output_dir, ".docker")
        os.makedirs(self.dockerfiles_dir, exist_ok=True)
        
    def _generate_dockerfile(self, iac_tool: str, project_dir: str, sns_arn: str) -> str:
        """Generates a minimal Dockerfile for the specific IaC tool."""
        
        # Base image
        dockerfile_content = [
            "FROM python:3.12-slim",
            "ENV DEBIAN_FRONTEND=noninteractive",
            "WORKDIR /workspace",
            "RUN apt-get update && apt-get install -y curl unzip wget git && rm -rf /var/lib/apt/lists/*",
            "RUN pip install --no-cache-dir boto3"
        ]
        
        # Install specific IaC tool
        if iac_tool == "terraform":
            dockerfile_content.extend([
                "RUN wget https://releases.hashicorp.com/terraform/1.8.0/terraform_1.8.0_linux_amd64.zip && \\",
                "    unzip terraform_1.8.0_linux_amd64.zip -d /usr/local/bin && \\",
                "    rm terraform_1.8.0_linux_amd64.zip"
            ])
        elif iac_tool == "opentofu":
            dockerfile_content.extend([
                "RUN wget https://github.com/opentofu/opentofu/releases/download/v1.7.0/tofu_1.7.0_linux_amd64.tar.gz && \\",
                "    tar -xvf tofu_1.7.0_linux_amd64.tar.gz -C /usr/local/bin tofu && \\",
                "    rm tofu_1.7.0_linux_amd64.tar.gz"
            ])
        elif iac_tool == "ansible":
            dockerfile_content.extend([
                "RUN apt-get update && apt-get install -y sshpass && rm -rf /var/lib/apt/lists/*",
                "RUN pip install --no-cache-dir ansible"
            ])
        elif iac_tool == "pulumi":
            dockerfile_content.extend([
                "RUN curl -fsSL https://get.pulumi.com | sh",
                "ENV PATH=$PATH:/root/.pulumi/bin"
            ])
        
        # Copy scripts and source code
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        rel_project_dir = os.path.relpath(project_dir, root_dir)
        
        dockerfile_content.extend([
            "COPY src/scripts/drift_detector.py /workspace/drift_detector.py",
            f"COPY {rel_project_dir} /workspace/iac_source"
        ])
        
        # Entrypoint configuration
        sns_arg = f"--sns-arn {sns_arn}" if sns_arn else ""
        dockerfile_content.extend([
            f'ENTRYPOINT ["python", "drift_detector.py", "--iac-dir", "/workspace/iac_source", "--iac-tool", "{iac_tool}"]'
            # Note: We append sns_arg in CMD so it can be overridden, or we bake it in.
            # Baking it into ENTRYPOINT for simplicity since it's an automated runner.
        ])
        
        # Add sns_arn if available
        if sns_arn:
            # Modify the last line to include sns-arn
            dockerfile_content[-1] = f'ENTRYPOINT ["python", "drift_detector.py", "--iac-dir", "/workspace/iac_source", "--iac-tool", "{iac_tool}", "--sns-arn", "{sns_arn}"]'

        # Write Dockerfile
        project_name = os.path.basename(os.path.normpath(project_dir))
        dockerfile_path = os.path.join(self.dockerfiles_dir, f"Dockerfile.{iac_tool}.{project_name}")
        
        with open(dockerfile_path, 'w') as f:
            f.write("\n".join(dockerfile_content) + "\n")
            
        return dockerfile_path

    def build_image(self, iac_tool: str, project_dir: str, sns_arn: str) -> str:
        """Generates the Dockerfile and builds the image."""
        project_name = os.path.basename(os.path.normpath(project_dir))
        image_name = f"iac-drift-guardian-{iac_tool}-{project_name}:latest".lower()
        
        dockerfile_path = self._generate_dockerfile(iac_tool, project_dir, sns_arn)
        
        logger.info(f"Building Docker image {click.style(image_name, fg='cyan')} for {iac_tool.upper()}...")
        
        try:
            # We must run this from the root of the project to get `src/scripts` and the dynamic `project_dir`
            # `project_dir` should be relative to the root or absolute.
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            
            # Subprocess to run docker build
            # Note: using `docker build -f Dockerfile_path .`
            command = [
                "docker", "build", 
                "-t", image_name, 
                "-f", dockerfile_path, 
                root_dir
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Docker build failed:\n{result.stderr}")
                return None
                
            logger.info(f"✔ Successfully built {image_name}")
            return image_name
            
        except FileNotFoundError:
            logger.error("Docker is not installed or not running. Please install Docker to use this feature.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during docker build: {e}")
            return None
