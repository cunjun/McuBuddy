from McuBuddy import codex_integration
from McuBuddy.codex_integration import inspect_codex_integration, remove_codex, setup_codex


class _Runner:
    def __init__(self, registered=False):
        self.registered = registered
        self.calls = []

    def __call__(self, command):
        self.calls.append(command)
        if command[-3:] == ["mcp", "get", "mcubuddy"]:
            return {
                "returncode": 0 if self.registered else 1,
                "stdout": "mcubuddy enabled" if self.registered else "",
                "stderr": "" if self.registered else "not found",
            }
        if "add" in command:
            self.registered = True
            return {"returncode": 0, "stdout": "added", "stderr": ""}
        if "remove" in command:
            self.registered = False
            return {"returncode": 0, "stdout": "removed", "stderr": ""}
        raise AssertionError(command)


class _ClaudeRunner(_Runner):
    def __call__(self, command):
        self.calls.append(command)
        if command[-3:] == ["mcp", "get", "mcubuddy"]:
            return {
                "returncode": 0 if self.registered else 1,
                "stdout": "mcubuddy enabled" if self.registered else "",
                "stderr": "" if self.registered else "not found",
            }
        if "add" in command:
            self.registered = True
            return {"returncode": 0, "stdout": "added", "stderr": ""}
        if "remove" in command:
            self.registered = False
            return {"returncode": 0, "stdout": "removed", "stderr": ""}
        raise AssertionError(command)


def _checkout(tmp_path):
    root = tmp_path / "McuBuddy"
    executable = root / ".venv" / "Scripts" / "McuBuddy.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    skill = root / "skills" / "mcubuddy"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# mcubuddy\n", encoding="utf-8")
    return root, executable


def test_status_reports_missing_registration_without_writing(tmp_path):
    root, executable = _checkout(tmp_path)
    runner = _Runner(registered=False)

    result = inspect_codex_integration(repo_root=root, runner=runner, codex_command="codex")

    assert result["status"] == "not_configured"
    assert result["executable"] == str(executable.resolve())
    assert len(runner.calls) == 1


def test_setup_registers_probe_and_diagnose_and_installs_skill(tmp_path):
    root, executable = _checkout(tmp_path)
    home = tmp_path / "home"
    runner = _Runner(registered=False)

    result = setup_codex(
        repo_root=root,
        home=home,
        toolsets=["probe", "diagnose"],
        confirm=True,
        runner=runner,
        codex_command="codex",
    )

    assert result["status"] == "ok"
    assert (home / ".codex" / "skills" / "mcubuddy" / "SKILL.md").is_file()
    add = next(call for call in runner.calls if "add" in call)
    assert add == [
        "codex", "mcp", "add", "mcubuddy",
        "--env", "MCUBUDDY_TOOLSETS=probe,diagnose",
        "--", str(executable.resolve()), "serve",
    ]
    assert result["restart_required"] is True


def test_setup_requires_confirmation_before_user_level_writes(tmp_path):
    root, _ = _checkout(tmp_path)
    runner = _Runner(registered=False)

    result = setup_codex(repo_root=root, confirm=False, runner=runner, codex_command="codex")

    assert result["status"] == "needs_confirmation"
    assert len(runner.calls) == 1


def test_repair_replaces_existing_registration(tmp_path):
    root, _ = _checkout(tmp_path)
    runner = _Runner(registered=True)

    result = setup_codex(
        repo_root=root,
        home=tmp_path / "home",
        confirm=True,
        repair=True,
        runner=runner,
        codex_command="codex",
    )

    assert result["status"] == "ok"
    assert any("remove" in call for call in runner.calls)
    assert any("add" in call for call in runner.calls)


def test_remove_requires_confirmation_and_removes_registration(tmp_path):
    runner = _Runner(registered=True)

    preview = remove_codex(confirm=False, runner=runner, codex_command="codex")
    removed = remove_codex(confirm=True, runner=runner, codex_command="codex")

    assert preview["status"] == "needs_confirmation"
    assert removed["status"] == "ok"
    assert any("remove" in call for call in runner.calls)


def test_setup_works_from_installed_package_without_source_checkout(monkeypatch, tmp_path):
    skill = tmp_path / "package" / "resources" / "mcubuddy_skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# mcubuddy\n", encoding="utf-8")
    executable = tmp_path / "bin" / "McuBuddy.exe"
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")
    runner = _Runner(registered=False)
    monkeypatch.setattr(
        "McuBuddy.codex_integration.inspect_runtime_installation",
        lambda: {"source_checkout": None},
    )
    monkeypatch.setattr(
        "McuBuddy.codex_integration._resolve_bundled_skill",
        lambda: skill,
    )
    monkeypatch.setattr(
        "McuBuddy.codex_integration.shutil.which",
        lambda name: str(executable) if name == "McuBuddy" else None,
    )

    result = setup_codex(
        home=tmp_path / "home",
        confirm=True,
        runner=runner,
        codex_command="codex",
    )

    assert result["status"] == "ok"
    assert result["repo_root"] is None
    assert result["skill_source"] == str(skill.resolve())
    assert (tmp_path / "home" / ".codex" / "skills" / "mcubuddy" / "SKILL.md").is_file()


def test_claude_status_reports_missing_registration_without_writing(tmp_path):
    root, executable = _checkout(tmp_path)
    runner = _ClaudeRunner(registered=False)

    result = codex_integration.inspect_claude_integration(
        repo_root=root,
        runner=runner,
        claude_command="claude",
    )

    assert result["status"] == "not_configured"
    assert result["executable"] == str(executable.resolve())
    assert runner.calls == [["claude", "mcp", "get", "mcubuddy"]]


def test_claude_setup_registers_user_mcp_and_installs_skill(tmp_path):
    root, executable = _checkout(tmp_path)
    home = tmp_path / "home"
    runner = _ClaudeRunner(registered=False)

    result = codex_integration.setup_claude(
        repo_root=root,
        home=home,
        toolsets=["probe", "diagnose"],
        confirm=True,
        runner=runner,
        claude_command="claude",
    )

    assert result["status"] == "ok"
    assert (home / ".claude" / "skills" / "mcubuddy" / "SKILL.md").is_file()
    add = next(call for call in runner.calls if "add" in call)
    assert add == [
        "claude",
        "mcp",
        "add",
        "--scope",
        "user",
        "--env",
        "MCUBUDDY_TOOLSETS=probe,diagnose",
        "mcubuddy",
        "--",
        str(executable.resolve()),
        "serve",
    ]
    assert result["restart_required"] is True


def test_claude_setup_requires_confirmation_before_user_level_writes(tmp_path):
    root, _ = _checkout(tmp_path)
    runner = _ClaudeRunner(registered=False)

    result = codex_integration.setup_claude(
        repo_root=root,
        confirm=False,
        runner=runner,
        claude_command="claude",
    )

    assert result["status"] == "needs_confirmation"
    assert runner.calls == [["claude", "mcp", "get", "mcubuddy"]]


def test_claude_repair_replaces_user_registration(tmp_path):
    root, _ = _checkout(tmp_path)
    runner = _ClaudeRunner(registered=True)

    result = codex_integration.setup_claude(
        repo_root=root,
        home=tmp_path / "home",
        confirm=True,
        repair=True,
        runner=runner,
        claude_command="claude",
    )

    assert result["status"] == "ok"
    assert ["claude", "mcp", "remove", "--scope", "user", "mcubuddy"] in runner.calls
    assert any("add" in call for call in runner.calls)


def test_claude_remove_requires_confirmation_and_removes_user_registration():
    runner = _ClaudeRunner(registered=True)

    preview = codex_integration.remove_claude(
        confirm=False, runner=runner, claude_command="claude"
    )
    removed = codex_integration.remove_claude(
        confirm=True, runner=runner, claude_command="claude"
    )

    assert preview["status"] == "needs_confirmation"
    assert removed["status"] == "ok"
    assert ["claude", "mcp", "remove", "--scope", "user", "mcubuddy"] in runner.calls
