"""Routine hourly snapshots rotate; milestone backups never do."""
import pytest

from scripts.prune_backups import prune, protected, routine_snapshots


def make(root, name, payload=b"x" * 16):
    directory = root / name
    directory.mkdir()
    (directory / "history.sqlite").write_bytes(payload)
    return directory


@pytest.fixture
def workflow(tmp_path):
    root = tmp_path / "workflow"
    root.mkdir()
    for stamp in ("20261026_080000", "20261026_090000", "20261026_100000"):
        make(root, f"grade_{stamp}")
    # Milestones in the same folder, deliberately older than the routine ones.
    make(root, "grade_20261001_milestone")       # does not match the pattern
    make(root, "refresh_20261026_112404")
    make(root, "task2_codex_review")
    return root


def test_only_the_routine_pattern_is_eligible(workflow):
    names = [d.name for d in routine_snapshots(workflow)]
    assert names == ["grade_20261026_080000", "grade_20261026_090000",
                     "grade_20261026_100000"]
    assert "grade_20261001_milestone" in protected(workflow)
    assert "refresh_20261026_112404" in protected(workflow)
    assert "task2_codex_review" in protected(workflow)


def test_keeps_newest_and_removes_oldest(workflow):
    result = prune(keep=2, dry_run=False, root=workflow)
    assert [name for name, _ in result["removed"]] == ["grade_20261026_080000"]
    assert (workflow / "grade_20261026_090000").is_dir()
    assert (workflow / "grade_20261026_100000").is_dir()
    assert not (workflow / "grade_20261026_080000").exists()


def test_milestones_survive_a_prune(workflow):
    prune(keep=1, dry_run=False, root=workflow)
    for name in ("grade_20261001_milestone", "refresh_20261026_112404",
                 "task2_codex_review"):
        assert (workflow / name).is_dir(), name


def test_dry_run_deletes_nothing(workflow):
    result = prune(keep=1, dry_run=True, root=workflow)
    assert len(result["removed"]) == 2
    assert len(routine_snapshots(workflow)) == 3


def test_nothing_to_do_when_under_the_limit(workflow):
    result = prune(keep=10, dry_run=False, root=workflow)
    assert result["removed"] == []
    assert result["kept"] == 3


def test_rejects_a_zero_keep(workflow):
    with pytest.raises(ValueError):
        prune(keep=0, dry_run=True, root=workflow)
