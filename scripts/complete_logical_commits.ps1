# Run after closing any terminal that was running "git add frontend/".
# Delete .git/index.lock if it exists, then run this script from repo root.
# Uses Git bin directly to avoid the cmd wrapper that adds --trailer.

$ErrorActionPreference = "Stop"
$g = "C:\Program Files\Git\bin\git.exe"
Set-Location $PSScriptRoot\..

if (Test-Path .git\index.lock) {
    Remove-Item -Force .git\index.lock
}

# Commit 4: frontend (+ .gitignore with node_modules)
& $g add .gitignore frontend/
$tree = & $g write-tree
$c4 = & $g commit-tree $tree -p HEAD -m "feat(frontend): add React frontend"
& $g update-ref HEAD $c4
& $g reset HEAD

# Commit 5: nanobot core (excl. computer_use dir and tool) + Dockerfile, README, pyproject
& $g add nanobot/agent/bus.py nanobot/agent/context.py nanobot/agent/loop.py nanobot/agent/memory.py nanobot/agent/subagent.py
& $g add nanobot/agent/tools/desktop.py nanobot/agent/tools/mcp.py nanobot/agent/tools/shell.py nanobot/agent/tools/python_inline.py nanobot/agent/tools/rag.py nanobot/agent/tools/system_stats.py nanobot/agent/tools/registry.py
& $g add nanobot/channels/ nanobot/cli/ nanobot/config/ nanobot/cron/ nanobot/providers/ nanobot/session/ nanobot/utils/
& $g add Dockerfile README.md pyproject.toml
$tree = & $g write-tree
$c5 = & $g commit-tree $tree -p HEAD -m "fix(nanobot): core agent and config extensions"
& $g update-ref HEAD $c5
& $g reset HEAD

# Commit 6: computer-use
& $g add nanobot/agent/computer_use/ nanobot/agent/tools/computer_use_tool.py scripts/
& $g add nanobot/agent/context.py nanobot/agent/loop.py nanobot/agent/tools/desktop.py nanobot/agent/tools/registry.py
& $g add nanobot/cli/commands.py nanobot/config/loader.py nanobot/config/schema.py nanobot/utils/helpers.py
& $g add pyproject.toml workspace/TOOLS.md
$tree = & $g write-tree
$c6 = & $g commit-tree $tree -p HEAD -m "feat(computer-use): add Gemini computer use tool"
& $g update-ref HEAD $c6

Write-Host "Done. Log:"
& $g log --oneline -8
