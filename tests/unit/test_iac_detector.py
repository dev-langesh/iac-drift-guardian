import pytest
import os
import shutil
from src.lib.iac.detector import (
    TerraformDetector, OpenTofuDetector, PulumiDetector, AnsibleDetector
)

@pytest.fixture
def temp_dir(tmp_path):
    d = tmp_path / "iac_test"
    d.mkdir()
    return d

def test_terraform_detection(temp_dir):
    detector = TerraformDetector()
    # No files
    assert detector.detect(str(temp_dir)) is False
    
    # Valid .tf file with content
    tf_file = temp_dir / "main.tf"
    tf_file.write_text('resource "aws_instance" "web" {}')
    assert detector.detect(str(temp_dir)) is True
    
    # Empty .tf file (regex should fail)
    tf_file.write_text('')
    assert detector.detect(str(temp_dir)) is False

def test_pulumi_detection(temp_dir):
    detector = PulumiDetector()
    # Pulumi.yaml signature
    (temp_dir / "Pulumi.yaml").write_text("name: test")
    assert detector.detect(str(temp_dir)) is True
    
    # Remove Pulumi.yaml and try code signature
    os.remove(temp_dir / "Pulumi.yaml")
    (temp_dir / "main.py").write_text("import pulumi\nprint('hello')")
    assert detector.detect(str(temp_dir)) is True

def test_ansible_detection(temp_dir):
    detector = AnsibleDetector()
    # Playbook signature
    (temp_dir / "playbook.yml").write_text("hosts: all\ntasks: []")
    assert detector.detect(str(temp_dir)) is True
    
    # Invalid YAML content
    (temp_dir / "playbook.yml").write_text("hello: world")
    assert detector.detect(str(temp_dir)) is False

def test_opentofu_detection(temp_dir):
    detector = OpenTofuDetector()
    # .tofu signature
    (temp_dir / "main.tofu").write_text('resource "null_resource" "test" {}')
    assert detector.detect(str(temp_dir)) is True

def test_engine_detect_multi(temp_dir):
    from src.lib.iac.detector import PlatformDetectionEngine
    # Create two subdirs with different IaC
    tf_dir = temp_dir / "tf"
    tf_dir.mkdir()
    (tf_dir / "main.tf").write_text('resource "aws_instance" "test" {}')
    
    ansible_dir = temp_dir / "ansible"
    ansible_dir.mkdir()
    (ansible_dir / "playbook.yml").write_text("hosts: all\ntasks: []")
    
    engine = PlatformDetectionEngine()
    results = engine.detect(str(temp_dir))
    assert len(results) == 2
    platforms = [r[0] for r in results]
    assert "terraform" in platforms
    assert "ansible" in platforms

def test_engine_select_projects_single(temp_dir):
    from src.lib.iac.detector import PlatformDetectionEngine
    engine = PlatformDetectionEngine()
    detected = [("terraform", str(temp_dir))]
    # Single project should return immediately without prompt
    selected = engine.select_projects(str(temp_dir), detected)
    assert selected == detected

def test_engine_select_projects_multi(temp_dir):
    from src.lib.iac.detector import PlatformDetectionEngine
    from unittest.mock import patch, MagicMock
    
    engine = PlatformDetectionEngine()
    detected = [("terraform", "/path/a"), ("ansible", "/path/b")]
    
    with patch('inquirer.prompt') as mock_prompt:
        mock_prompt.return_value = {'projects': [("terraform", "/path/a")]}
        
        selected = engine.select_projects(str(temp_dir), detected)
        assert len(selected) == 1
        assert selected[0][0] == "terraform"
