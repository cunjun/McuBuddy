from __future__ import annotations

from pathlib import Path

from McuBuddy.tool_catalog_docs import render_tool_catalog_markdown


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output = repo_root / "docs" / "tool-catalog.generated.md"
    output.write_text(render_tool_catalog_markdown(), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
