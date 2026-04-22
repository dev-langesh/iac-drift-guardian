import os
import pytest
import shutil
from src.lib.git.handler import GitHandler

@pytest.fixture
def temp_dirs():
    dirs = {
        'source': os.path.abspath('tests/integration/tmp_source'),
        'dest': os.path.abspath('tests/integration/tmp_dest')
    }
    for d in dirs.values():
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    yield dirs
    # Cleanup
    for d in dirs.values():
        if os.path.exists(d):
            shutil.rmtree(d)

def test_local_path_verification(temp_dirs):
    # This is more about how main handles it, but we can verify our handler's utility
    assert os.path.isabs(temp_dirs['source'])
    assert os.path.isdir(temp_dirs['source'])

def test_real_clone_small_repo(temp_dirs):
    handler = GitHandler()
    # Using a very small, stable repo for integration testing
    repo_url = "https://github.com/octocat/Spoon-Knife.git"
    repo = handler.clone(repo_url, temp_dirs['dest'])
    assert repo is not None
    assert os.path.exists(os.path.join(temp_dirs['dest'], 'index.html'))
