from __future__ import annotations

import json

from McuBuddy.installation_registry import (
    clear_installation_home,
    get_installation_home,
    set_installation_home,
)


def _make_checkout(root):
    (root / "src" / "McuBuddy").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "McuBuddy"\n',
        encoding="utf-8",
    )
    executable = root / ".venv" / "Scripts" / "McuBuddy.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    return executable


def test_set_installation_home_requires_confirmation(tmp_path) -> None:
    checkout = tmp_path / "McuBuddy"
    _make_checkout(checkout)

    report = set_installation_home(checkout, home=tmp_path, confirm=False)

    assert report["status"] == "needs_confirmation"
    assert not (tmp_path / ".mcubuddy" / "installations.json").exists()


def test_set_and_get_installation_home(tmp_path) -> None:
    checkout = tmp_path / "McuBuddy"
    executable = _make_checkout(checkout)

    saved = set_installation_home(checkout, home=tmp_path, confirm=True)
    loaded = get_installation_home(home=tmp_path)

    assert saved["status"] == "ok"
    assert loaded["status"] == "ok"
    assert loaded["installation"]["repo_root"] == str(checkout.resolve())
    assert loaded["installation"]["executable"] == str(executable.resolve())

    raw = json.loads(
        (tmp_path / ".mcubuddy" / "installations.json").read_text(encoding="utf-8")
    )
    assert raw["schema_version"] == "1.0"
    assert raw["default"]["repo_root"] == str(checkout.resolve())


def test_set_installation_home_rejects_non_mcubuddy_directory(tmp_path) -> None:
    unrelated = tmp_path / "other"
    unrelated.mkdir()

    report = set_installation_home(unrelated, home=tmp_path, confirm=True)

    assert report["status"] == "error"
    assert "McuBuddy checkout" in report["summary"]


def test_clear_installation_home_requires_confirmation(tmp_path) -> None:
    checkout = tmp_path / "McuBuddy"
    _make_checkout(checkout)
    set_installation_home(checkout, home=tmp_path, confirm=True)

    preview = clear_installation_home(home=tmp_path, confirm=False)

    assert preview["status"] == "needs_confirmation"
    assert get_installation_home(home=tmp_path)["status"] == "ok"


def test_clear_installation_home_removes_saved_default(tmp_path) -> None:
    checkout = tmp_path / "McuBuddy"
    _make_checkout(checkout)
    set_installation_home(checkout, home=tmp_path, confirm=True)

    cleared = clear_installation_home(home=tmp_path, confirm=True)

    assert cleared["status"] == "ok"
    assert get_installation_home(home=tmp_path)["status"] == "not_configured"
