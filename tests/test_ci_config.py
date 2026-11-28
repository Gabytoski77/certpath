"""CI config checks: the secret scan must only look at the branch being tested."""
import pathlib
import re

WORKFLOWS = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"


def test_gitleaks_git_is_scoped_to_head():
    found = False
    for wf in sorted(WORKFLOWS.glob("*.y*ml")):
        for line in wf.read_text().splitlines():
            if re.search(r"gitleaks\"?\s+git\b", line):
                found = True
                assert "--log-opts" in line, f"{wf.name}: `gitleaks git` needs --log-opts=\"HEAD\": {line.strip()}"
    assert found, "no `gitleaks git` step found; update this test if the scan moved"
