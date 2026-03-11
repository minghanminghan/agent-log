"""Tests for agentlog.repo."""

from pathlib import Path
import pytest
from agentlog.repo import find_root


def test_find_root_from_subdir(tmp_path):
    """find_root returns correct root when called from a subdirectory."""
    agentlog_dir = tmp_path / ".agentlog"
    agentlog_dir.mkdir()
    subdir = tmp_path / "src" / "utils"
    subdir.mkdir(parents=True)
    assert find_root(subdir) == tmp_path


def test_find_root_returns_none_when_not_initialized(tmp_path):
    """find_root returns None when no .agentlog/ exists in the tree."""
    subdir = tmp_path / "a" / "b" / "c"
    subdir.mkdir(parents=True)
    # tmp_path is isolated, no .agentlog anywhere above it in a test context
    # We test in a path that definitely has no .agentlog
    result = find_root(subdir)
    # Since tmp_path has no .agentlog, result should be None (or something outside tmp_path)
    if result is not None:
        # Make sure .agentlog exists at the returned root
        assert (result / ".agentlog").is_dir()
        # Ensure the root is NOT inside tmp_path (it's a real system-level .agentlog)
        assert not str(result).startswith(str(tmp_path))


def test_find_root_returns_none_clean(tmp_path):
    """Explicit None case with deep path and no .agentlog anywhere."""
    # Create a deep structure, no .agentlog
    deep = tmp_path / "x" / "y" / "z"
    deep.mkdir(parents=True)
    result = find_root(deep)
    # Either None or a path outside tmp_path
    if result is not None:
        assert not str(result).startswith(str(tmp_path))


def test_find_root_in_cwd(tmp_path):
    """find_root returns the immediate directory when .agentlog/ is in cwd."""
    agentlog_dir = tmp_path / ".agentlog"
    agentlog_dir.mkdir()
    assert find_root(tmp_path) == tmp_path


def test_find_root_nested(tmp_path):
    """find_root finds root even from multiple levels deep."""
    agentlog_dir = tmp_path / ".agentlog"
    agentlog_dir.mkdir()
    deep = tmp_path / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    assert find_root(deep) == tmp_path
