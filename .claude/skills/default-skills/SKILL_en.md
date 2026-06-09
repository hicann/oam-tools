---
name: default-skills
description: |
  **Scenarios that must trigger this default-skills** (use when user mentions any of the following): cannot find/missing/install/update gitcode-pr, gitcode-issue skill, or install required/default/necessary/essential skills;
---

## Install Default Skills Steps
1. Read `.claude/skills/default-skills/scripts/install-default-skills.sh` to get `DEFAULT_SKILLS`
2. First try to install missing skills using `.claude/skills/default-skills/scripts/install-default-skills.sh`. **This script first checks whether each skill already exists under the repo's `.claude/skills/`: any already-present skill is skipped — neither downloaded nor overwritten — to protect local modifications in this repo; only skills missing from this repo are downloaded and installed.** After execution, check if `.claude/skills/` directory has `DEFAULT_SKILLS`. If yes, end immediately. If no, continue to next step
3. Use git to clone `https://gitcode.com/cann-agent/skills.git` to temporary directory with `--depth 1` parameter. Find the **skills missing from this repo** among `DEFAULT_SKILLS` and copy to `.claude/skills/` directory (**do not overwrite skills already present in this repo**)

## Default Skills Usage Scenarios
1. **Scenarios that must trigger gitcode-issue** (use when user mentions any of the following):
- View/Read issue: view issue, check issue, read issue, open issue, issue details, what is issue
- GitCode URL: gitcode.com/**/issues/**, cann/oam-tools/issues, issue link
- Direct mention of number: issue 123, #123, problem 123
- View comments: issue comments, comment content

2. **Scenarios that must trigger gitcode-pr** (use when user mentions any of the following):
- Create/Submit PR: create PR, make a PR, submit PR, generate PR, need PR, pull request, merge request
- Push code to remote: push code, push code, push code up, submit to remote, push to gitcode, submit code to GitCode
- Merge request: merge request, code merge request, request merge, merge request
- PR template/description: PR template, PR description, PR format
- Create PR associated with issue: PR with issue, create PR associated with issue
- Get PR changes: view PR changes, PR file list, what PR changed, view PR diff, get PR files
- **Get PR comments**: view PR comments, PR comments, get comments, read comments
- **View PR discussions**: PR discussions, view discussions, discussions
- **Delete PR comments**: delete comments, delete PR comments, remove comments, delete comment, remove this comment