from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_wheel_force_includes_mcubuddy_skill_as_package_resource() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)

    force_include = config["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert force_include["skills/mcubuddy"] == "McuBuddy/resources/mcubuddy_skill"


def test_docs_explain_setup_without_git_checkout() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "PROJECT_GUIDE.md").read_text(encoding="utf-8")

    for text in (readme, guide):
        assert "uv tool install McuBuddy" in text
        assert "McuBuddy setup codex --confirm --json" in text
    assert "do not need a Git checkout" in guide
