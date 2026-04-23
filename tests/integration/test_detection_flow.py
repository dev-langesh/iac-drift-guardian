import os
import pytest
from src.lib.iac.detector import PlatformDetectionEngine

@pytest.fixture
def engine():
    return PlatformDetectionEngine()

@pytest.mark.parametrize("platform, case_type, expected_platform", [
    ("terraform", "root", "terraform"),
    ("terraform", "nested", "terraform"),
    ("ansible", "root", "ansible"),
    ("ansible", "nested", "ansible"),
    ("opentofu", "root", "opentofu"),
    ("opentofu", "nested", "opentofu"),
    ("pulumi", "root", "pulumi"),
    ("pulumi", "nested", "pulumi"),
])
def test_all_platforms_and_cases(engine, platform, case_type, expected_platform):
    # Construct path based on the created sample_projects
    base_path = f"sample_projects/{platform}/{case_type}"
    abs_path = os.path.abspath(base_path)
    
    result = engine.detect(abs_path, max_depth=2)
    assert len(result) > 0
    detected_platform, project_dir = result[0]
    
    assert detected_platform == expected_platform
    if case_type == "nested":
        assert abs_path != project_dir # Should be in a subfolder
    else:
        assert abs_path == project_dir # Should be in the root

def test_manual_fallback_refusal(engine):
    # Test a directory with no IaC and refusal to manually specify
    abs_path = os.path.abspath("sample_projects/empty")
    if not os.path.exists(abs_path):
        os.makedirs(abs_path)
        with open(os.path.join(abs_path, "README.md"), "w") as f:
            f.write("test")

    from unittest.mock import patch
    with patch('click.confirm', return_value=False):
        detected_list = engine.detect(abs_path, max_depth=2)
        assert len(detected_list) == 0
        result = engine.select_projects(abs_path, detected_list)
        assert result == []

def test_multi_project_detection(engine):
    # This uses the sample_projects/multi directory created earlier
    abs_path = os.path.abspath("sample_projects/multi")
    
    result = engine.detect(abs_path, max_depth=2)
    # It should find 5 projects
    assert len(result) == 5
    for platform, path in result:
        assert any(x in platform for x in ["terraform", "opentofu", "ansible", "pulumi"])
        assert any(x in path for x in ["ec2", "fanout", "tofu","ansible", "pulumi"])
