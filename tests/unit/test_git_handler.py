import pytest
from unittest.mock import patch, MagicMock
from src.lib.git.handler import GitHandler
import subprocess

@pytest.fixture
def handler():
    return GitHandler()

def test_is_git_installed(handler):
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert handler.is_git_installed() is True

def test_is_git_not_installed(handler):
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError()
        assert handler.is_git_installed() is False

def test_is_valid_git_url(handler):
    assert handler.is_valid_git_url("https://github.com/user/repo.git") is True
    assert handler.is_valid_git_url("git@github.com:user/repo.git") is True
    assert handler.is_valid_git_url("/abs/path") is False
    assert handler.is_valid_git_url("invalid") is False

@patch('subprocess.run')
def test_verify_access_success(mock_run, handler):
    mock_run.return_value = MagicMock(returncode=0)
    success, pat = handler.verify_access("https://github.com/user/repo")
    assert success is True
    assert pat is None

@patch('subprocess.run')
@patch('click.prompt')
def test_verify_access_denied_then_success(mock_prompt, mock_run, handler):
    # First call fails with auth error, second succeeds
    mock_run.side_effect = [
        subprocess.CalledProcessError(128, "git ls-remote", stderr=b"Authentication failed"),
        MagicMock(returncode=0)
    ]
    mock_prompt.return_value = "secret_pat"
    
    success, pat = handler.verify_access("https://github.com/user/repo")
    assert success is True
    assert pat == "secret_pat"
    assert mock_run.call_count == 2

@patch('subprocess.run')
@patch('click.confirm')
@patch('click.prompt')
def test_verify_access_not_found_private(mock_prompt, mock_confirm, mock_run, handler):
    # First call returns 'not found', user confirms private, enters PAT, second succeeds
    mock_run.side_effect = [
        subprocess.CalledProcessError(128, "git ls-remote", stderr=b"Repository not found"),
        MagicMock(returncode=0)
    ]
    mock_confirm.return_value = True
    mock_prompt.return_value = "new_pat"
    
    success, pat = handler.verify_access("https://github.com/user/repo")
    assert success is True
    assert pat == "new_pat"
    assert mock_run.call_count == 2
    assert mock_confirm.called

def test_prepare_url_injection(handler):
    url = "https://github.com/user/repo"
    assert handler._prepare_url(url, "token") == "https://token@github.com/user/repo"
    assert handler._prepare_url("git@github.com:user/repo", "token") == "git@github.com:user/repo"

@patch('os.path.exists')
@patch('os.listdir')
@patch('src.lib.git.handler.Repo')
@patch('inquirer.prompt')
def test_clone_existing_repo_pull_success(mock_inquirer_prompt, mock_repo_cls, mock_listdir, mock_exists, handler):
    mock_exists.return_value = True
    mock_listdir.return_value = ["file"]
    
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.is_dirty.return_value = False
    
    # Mock origin and its URL
    mock_origin = MagicMock()
    mock_origin.url = "https://github.com/user/repo"
    mock_repo.remotes.origin = mock_origin
    
    # Mock user choosing "pull"
    mock_inquirer_prompt.return_value = {'action': 'pull'}
    
    result = handler.clone("https://github.com/user/repo", "/some/path")
    assert result == "/some/path"
    mock_origin.pull.assert_called_once()

@patch('os.path.exists')
@patch('os.listdir')
@patch('src.lib.git.handler.Repo')
@patch('inquirer.prompt')
@patch('click.prompt')
def test_clone_collision_new_name(mock_click_prompt, mock_inquirer_prompt, mock_repo_cls, mock_listdir, mock_exists, handler):
    # Scenario: Directory exists but is not a matching repo. User chooses "new name".
    mock_exists.side_effect = [True, False] # First call exists, second (recursed) does not
    mock_listdir.return_value = ["random_file"]
    mock_repo_cls.side_effect = Exception("Not a git repo")
    
    mock_inquirer_prompt.return_value = {'action': 'new'}
    mock_click_prompt.return_value = "new_dir"
    
    with patch('src.lib.git.handler.Repo.clone_from') as mock_clone:
        result = handler.clone("https://github.com/user/repo", "/base/old_dir")
        assert "new_dir" in result
        mock_clone.assert_called_once()

@patch('os.path.exists')
@patch('os.listdir')
@patch('shutil.rmtree')
@patch('inquirer.prompt')
@patch('click.confirm')
@patch('src.lib.git.handler.Repo.clone_from')
def test_clone_collision_override(mock_clone, mock_confirm, mock_inquirer, mock_rmtree, mock_listdir, mock_exists, handler):
    # Scenario: Directory exists. User chooses "override".
    mock_exists.side_effect = [True, False] # Exists, then after rmtree it doesn't
    mock_listdir.return_value = ["old_junk"]
    
    mock_inquirer.return_value = {'action': 'override'}
    mock_confirm.return_value = True
    
    result = handler.clone("https://github.com/user/repo", "/base/junk")
    assert result == "/base/junk"
    mock_rmtree.assert_called_once_with("/base/junk")
    mock_clone.assert_called_once()
