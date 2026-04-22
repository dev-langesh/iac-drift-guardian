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
