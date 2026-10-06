"""Git sandbox for the engineering workflow: clone, verify pushes and draft PRs.

The workflow pushes only to a repository made for the demo: a private GitHub
sandbox (demo.py sandbox-init, then demo.py live --sandbox-repo) or, by default,
a local bare repository under artifacts/. The seed branch is never pushed to.
"""
import json
from pathlib import Path
import subprocess
import tempfile

from catalog import ROOT
import portfolio

SEED_BRANCH = "main"
AUTHOR = ("DH-401 workflow agent", "workflow-agent@datahoney.invalid")
IGNORE = "__pycache__/\n*.pyc\n"


def run(cwd, *args, timeout=60):
    result = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])} failed: {(result.stderr or result.stdout).strip()[:400]}")
    return result.stdout.strip()


def git(cwd, *args, timeout=60):
    return run(cwd, "git", *args, timeout=timeout)


def remote_url(repo):
    return f"https://github.com/{repo}.git"


def _seed(directory):
    for relative, content in portfolio.inputs("DH-401", False).items():
        path = Path(directory) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (Path(directory) / ".gitignore").write_text(IGNORE)
    git(directory, "init", "-q", "-b", SEED_BRANCH)
    git(directory, "-c", f"user.name={AUTHOR[0]}", "-c", f"user.email={AUTHOR[1]}", "add", ".")
    git(directory, "-c", f"user.name={AUTHOR[0]}", "-c", f"user.email={AUTHOR[1]}", "commit", "-q", "-m", "Seed: invoice exporter before DH-401")


def _use_gh_credentials(directory):
    # Repository-local only: pushes authenticate with the existing gh login; global git config is untouched.
    git(directory, "config", "--local", "--add", "credential.helper", "")
    git(directory, "config", "--local", "--add", "credential.helper", "!gh auth git-credential")


def init_github(repo):
    """Create the private sandbox if needed and (re)seed its main branch."""
    exists = subprocess.run(["gh", "repo", "view", repo, "--json", "name"], capture_output=True, text=True).returncode == 0
    if not exists:
        run(ROOT, "gh", "repo", "create", repo, "--private", "--description",
            "Synthetic sandbox for the Data Honey DH-401 engineering-workflow demo. Agents push branches and draft PRs here.")
    with tempfile.TemporaryDirectory(prefix="datahoney-sandbox-seed-") as temp:
        _seed(temp)
        git(temp, "remote", "add", "origin", remote_url(repo))
        _use_gh_credentials(temp)
        git(temp, "push", "-q", "--force", "origin", SEED_BRANCH, timeout=120)
    return f"https://github.com/{repo}"


def local_remote(directory=None):
    """A local bare repository seeded once; the offline default and the test remote."""
    bare = Path(directory or ROOT / "artifacts/sandbox/origin.git")
    if not (bare / "HEAD").exists():
        bare.parent.mkdir(parents=True, exist_ok=True)
        git(bare.parent, "init", "-q", "--bare", "-b", SEED_BRANCH, str(bare))
        with tempfile.TemporaryDirectory(prefix="datahoney-sandbox-seed-") as temp:
            _seed(temp)
            git(temp, "push", "-q", str(bare), SEED_BRANCH)
    return str(bare)


def checkout(remote, workspace, branch, github=False):
    git(Path(workspace).parent, "clone", "-q", "--branch", SEED_BRANCH, remote, str(workspace), timeout=120)
    git(workspace, "checkout", "-q", "-b", branch)
    git(workspace, "config", "--local", "user.name", AUTHOR[0])
    git(workspace, "config", "--local", "user.email", AUTHOR[1])
    if github:
        _use_gh_credentials(workspace)
    return git(workspace, "rev-parse", "HEAD")


def remote_head(workspace, branch):
    line = git(workspace, "ls-remote", "origin", f"refs/heads/{branch}", timeout=60)
    return line.split()[0] if line else None


def inspect(workspace, branch, base):
    """What the agent actually committed and pushed, checked against the remote."""
    head = git(workspace, "rev-parse", "HEAD")
    pushed = remote_head(workspace, branch)
    dirty = [line[3:] for line in git(workspace, "status", "--porcelain").splitlines()]
    files = git(workspace, "diff", "--name-only", f"{base}..{head}").splitlines()
    commits = [line.split(" ", 1) for line in git(workspace, "log", "--format=%h %s", f"{base}..{head}").splitlines()]
    return {"branch": branch, "head": head, "remote_head": pushed, "pushed": pushed == head, "clean": not dirty,
            "dirty": dirty, "files": files, "commits": [{"sha": sha, "subject": subject} for sha, subject in commits],
            "main_unchanged": remote_head(workspace, SEED_BRANCH) == base}


def detach(workspace):
    # The reviewer's disposable copy cannot push anywhere.
    for name in git(workspace, "remote").split():
        git(workspace, "remote", "remove", name)


def find_pr(repo, branch):
    output = run(ROOT, "gh", "pr", "list", "--repo", repo, "--head", branch, "--state", "all",
                 "--json", "number,url,isDraft,state,title")
    # Only an open PR counts; a closed one from an earlier attempt must not satisfy the check.
    items = [item for item in json.loads(output or "[]") if item.get("state") == "OPEN"]
    return items[0] if items else None


def mark_ready(repo, number):
    run(ROOT, "gh", "pr", "ready", str(number), "--repo", repo)
    return find_pr_by_number(repo, number)


def find_pr_by_number(repo, number):
    return json.loads(run(ROOT, "gh", "pr", "view", str(number), "--repo", repo, "--json", "number,url,isDraft,state,title"))


def branch_url(repo, branch):
    return f"https://github.com/{repo}/tree/{branch}" if repo else None

