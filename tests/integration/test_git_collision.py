import os
import pytest
import shutil
from src.lib.git.handler import GitHandler
from git import Repo

@pytest.fixture
def git_handler():
    return GitHandler()

@pytest.fixture
def temp_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return str(workspace)

def test_clone_and_then_pull(git_handler, temp_workspace):
    # 1. First clone
    repo_url = "https://github.com/dev-langesh/terraform.git"
    dest_dir = os.path.join(temp_workspace, "my_repo")
    
    # We'll use a real public repo for integration testing
    path = git_handler.clone(repo_url, dest_dir)
    assert path == dest_dir
    assert os.path.exists(os.path.join(dest_dir, ".git"))
    
    # 2. Second clone (should trigger pull prompt)
    from unittest.mock import patch
    with patch('inquirer.prompt') as mock_prompt:
        mock_prompt.return_value = {'action': 'pull'}
        path2 = git_handler.clone(repo_url, dest_dir)
        assert path2 == dest_dir

def test_collision_with_non_git_dir(git_handler, temp_workspace):
    # Create a non-git directory
    dest_dir = os.path.join(temp_workspace, "non_git")
    os.makedirs(dest_dir)
    with open(os.path.join(dest_dir, "file.txt"), "w") as f:
        f.write("hello")
        
    repo_url = "https://github.com/dev-langesh/terraform.git"
    
    # Mock inquirer to select "new" name
    from unittest.mock import patch
    with patch('inquirer.prompt') as mock_prompt, \
         patch('click.prompt') as mock_click_prompt:
        
        mock_prompt.return_value = {'action': 'new'}
        mock_click_prompt.return_value = "new_location"
        
        path = git_handler.clone(repo_url, dest_dir)
        assert "new_location" in path
        assert os.path.exists(path)
        assert os.path.exists(os.path.join(path, ".git"))
