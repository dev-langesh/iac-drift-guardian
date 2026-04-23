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
