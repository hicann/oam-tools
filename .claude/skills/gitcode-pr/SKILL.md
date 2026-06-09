---
name: gitcode-pr
description: |
  使用 GitCode API 创建 Pull Request 和获取 PR 评论。当用户需要**创建** GitCode PR、将代码**推送并创建合并请求**、**获取 PR 评论**、**查看 PR 讨论**、**查看 PR 改动**或**删除 PR 评论**时使用此 skill。支持读取普通评论和行内(diff)评论，包括评论内容、文件路径、代码行号等详细信息。
  **必须触发此 skill 的场景**（用户提到以下任何内容时使用）：
  - 创建/提交 PR：创建PR、提个PR、发PR、做个PR、帮我PR、生成PR、需要PR、pull request、merge request
  - 推送代码到远程：push代码、推代码、把代码推上去、提交到远程、推送到gitcode、提交代码到GitCode
  - 合并请求：合并请求、代码合入请求、请求合并、merge request
  - PR模板/描述：PR模板、PR描述、PR格式
  - 关联issue创建PR：关issue的PR、关联issue创建PR
  - 获取PR改动：查看PR变更、PR文件列表、PR改了什么、看PRdiff、获取PR文件
  - **获取 PR 评论**：查看PR评论、PR评论、获取评论、read comments
  - **查看 PR 讨论**：PR discussions、查看讨论、discussions
  - **删除 PR 评论**：删除评论、删除PR评论、移除评论、delete comment、移除这条评论
---

# GitCode PR Skill

创建 GitCode Pull Request 和获取 PR 评论的标准化流程。

## 强制约定：一律走脚本，禁止手写 curl/jq

**所有读写 PR 的操作必须调用 `scripts/pr_ops.py` 对应子命令，禁止手写 curl/jq。** 脚本已固化分页(per_page=100)、流水线终态筛选(排除"触发成功")、引用回复、v4→v5 回退、fork 来源校验等踩坑逻辑；手写 curl 会重新引入这些错误（漏分页、误判流水线结果、回复发错位置等本 skill 历史反复踩过的坑）。创建 PR 用 `scripts/create_pr.py`。

脚本能力速查（`--owner/--repo` 传 PR 目标仓，即 `resolve-repo` 输出的 `parent_owner/parent_repo`；token 取 `GITCODE_API_TOKEN`）：

| 子命令 | 用途 | 示例 |
|--------|------|------|
| `resolve-repo` | 探测 owner/repo 与 fork 目标仓 | `pr_ops.py resolve-repo` |
| `get-state` | 查 PR 状态(open/merged/closed) | `pr_ops.py get-state --pr N --owner O --repo R` |
| `get-pipeline` | 取最新流水线完成结果(支持 `--since`) | `pr_ops.py get-pipeline --pr N --owner O --repo R` |
| `get-codecheck` | 取 CI 结论(codecheck/precommit pass + commit_id) | `pr_ops.py get-codecheck --pr N --owner O --repo R` |
| `get-reviews` | 列出人类评审意见(排除 robot/自己/lgtm) | `pr_ops.py get-reviews --pr N --owner O --repo R --me ME` |
| `get-files` | 取 PR 文件变更 | `pr_ops.py get-files --pr N --owner O --repo R` |
| `reply` | 引用回复评审(普通评论) | `pr_ops.py reply --pr N --owner O --repo R --body-file F` |
| `review` | 发行内评审意见(绑定 文件:行号) | `pr_ops.py review --pr N --owner O --repo R --path P --line L --body-file F` |
| `update-pr` | 更新 PR 描述/标题 | `pr_ops.py update-pr --pr N --owner O --repo R --body-file F` |
| `trigger` | 触发 compile 流水线 | `pr_ops.py trigger --pr N --owner O --repo R` |
| `delete-comment` | 删除指定评论 | `pr_ops.py delete-comment --owner O --repo R --comment-id ID` |
| `issue-prs` | 查 issue 关联的 PR | `pr_ops.py issue-prs --owner O --repo R --issue N` |

脚本路径前缀 `python3 .claude/skills/gitcode-pr/scripts/`。`poll_pipeline.sh` 后台轮询见第 12-C 节。下文各节给出对应脚本调用；原始 API 细节见 `references/gitcode_api.md`，仅供排查/扩展脚本时查阅，日常操作不直接用。

## 工作流程

### 1. 获取访问令牌（第一步必须）

**询问用户**："请提供您的 GitCode 访问令牌（Access Token）"

检查环境变量：
```bash
echo $GITCODE_API_TOKEN
```

如果不存在，提示用户获取令牌：
1. 登录 [GitCode](https://gitcode.com)
2. 点击头像 → 设置 → 访问令牌
3. 创建新令牌，选择 `read_repository`、`write_repository` 和 `read_api` 权限
4. 复制令牌，建议保存到 `~/.bashrc`：`export GITCODE_API_TOKEN="your_token_here"`

### 2. 识别PR的目标仓库

#### 2.1 查询远程仓库

```bash
git remote -v
```

根据远程仓库 URL 确定目标仓库：
- **目标仓库**：PR 要合并到的仓库（通常是 origin 或 upstream）
- **源仓库**：当前工作分支所在的仓库

#### 2.2 提取仓库 owner/repo 信息

**关键**：所有 API 调用都需要使用当前仓库的 owner/repo，而非硬编码。

```bash
# 从远程 URL 提取 owner 和 repo
repo_url=$(git remote get-url origin)

# 处理不同 URL 格式
# SSH 格式: git@gitcode.com:owner/repo.git
# HTTPS 格式: https://gitcode.com/owner/repo.git
if [[ $repo_url == git@* ]]; then
  owner=$(echo $repo_url | sed 's|.*:\([^/]*\)/\([^/]*\)\.git$|\1|')
  repo=$(echo $repo_url | sed 's|.*:\([^/]*\)/\([^/]*\)\.git$|\2|')
else
  owner=$(echo $repo_url | sed 's|.*gitcode\.com/\([^/]*\)/\([^/]*\)\.git$|\1|')
  repo=$(echo $repo_url | sed 's|.*gitcode\.com/\([^/]*\)/\([^/]*\)\.git$|\2|')
fi

# URL 编码（用于 API 路径）
encoded_repo=$(printf '%s' "${owner}/${repo}" | jq -sRr @uri)

echo "Owner: $owner"
echo "Repo: $repo"
echo "Encoded: $encoded_repo"  # 例如: cann%2Fge
```

**后续所有 API 调用都应使用这些变量**：
- GitLab API v4 格式：`/projects/${encoded_repo}/...`
- GitHub API v5 格式：`/repos/${owner}/${repo}/...`

#### 2.3 查询 Fork 的原仓库（当当前仓库是 fork 时）

当当前仓库是 fork 时，PR 目标仓应为其 fork 来源（源仓）。**用脚本一步探测**（已固化 HTTP/jq 校验，查询失败报错退出、绝不静默回退当前仓）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py resolve-repo
```

返回：

```json
{
  "owner": "<当前fork owner>", "repo": "<当前fork repo>",
  "is_fork": true,
  "parent_owner": "<源仓owner>", "parent_repo": "<源仓repo>",
  "parent_encoded_repo": "<源仓owner%2Frepo>"
}
```

**后续约定**：
- 创建 PR / 查 PR 状态、评论、流水线等所有脚本调用的 `--owner/--repo` 一律传 `parent_owner/parent_repo`（源仓）。
- 非 fork（`is_fork=false`）时 `parent_*` 即当前仓，用法不变。

**响应关键字段**：
| 字段 | 说明 |
|------|------|
| `fork` | 是否为 fork 仓库（`true`/`false`） |
| `parent.full_name` | 原仓库完整名称（格式：`owner/repo`） |
| `parent.html_url` | 原仓库网页地址 |
| `parent.default_branch` | 原仓库默认分支 |

**默认目标仓库策略（重要）**：
- **当前仓库是 fork（`fork=true`）时，PR 默认创建到源仓（`parent.full_name`）**，而非当前 fork 仓。
- 创建 PR 时 API 路径中的 `${owner}/${repo}` 使用**源仓**，`head` 使用 `当前fork的owner:分支名` 形式进行跨仓提交。
- 仅当用户明确要求在 fork 仓内部提 PR 时，才使用当前 fork 仓作为目标。

**示例输出**：
```json
{
  "fork": true,
  "parent": {
    "full_name": "cann-agent/skills",
    "html_url": "https://gitcode.com/cann-agent/skills",
    "default_branch": "main"
  }
}
```

### 3. 获取 PR 评论和评审意见

**用脚本拉取人类评审意见**（已固化 per_page=100、排除 cann-robot/自己/`lgtm`-`approve`）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-reviews \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> --me <自己用户名>
```

返回 `{count, reviews:[{discussion_id, comment_type, user, created_at, body}]}`。

**字段说明**（解析时参考）：

| 字段 | 说明 |
|------|------|
| `comment_type` | `diff_comment`=行内评论，`pr_comment`=独立评论 |
| `discussion_id` | 讨论 ID |
| `user` | 评审者用户名 |
| `created_at` | 评论时间 |
| `body` | 评论内容 |

流水线/CI 结论不在此列，分别用 `get-pipeline`、`get-codecheck`（见第 12 节）。

### 4. 获取 PR 文件变更

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-files \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

返回 `{count, files:[{new_path, old_path}]}`。

### 5. 回复评审意见 / 发表行内评审意见

三种场景，**按评论类型选子命令**：
- **回复 `pr_comment`（总结/独立评论，挂不上线程）** → 用 `reply`（引用回复，见 5.1）。
- **作为评审者新发起行内意见**（绑定 diff 某一行）→ 用 `review`（见 5.2）。
- **回复 `diff_comment`（已有行内评论，可挂线程）** → 用 `reply-review`（见 5.3）。

#### 5.1 回复评审意见（引用回复，reply）

**适用对象：`pr_comment` 类型的总结/独立评论**（含机器人 `cann-tool-pr-reviewer` 的整轮结论）。这类评论**无法线程回复**——往其 discussion 回复会另起独立评论、不挂线程，故用引用回复：发一条普通 PR 评论，正文 `@评审者` 并用引用块（`>`）逐条摘录每条意见的 `文件:行号` + 原文，紧跟处理说明（已采纳/commit、替代方案、或不成立的理由），一一对应。

> 实测边界（按评论类型，不按是否机器人）：`diff_comment`（行内）**可线程回复**，用 5.3 `reply-review`（`in_thread=true` 已实测，机器人发起的行内评论同样可挂）；`pr_comment`（总结/独立）挂不上线程，用本节引用回复。

**用脚本发引用回复**（已固化 v5 普通评论 + 发后回查确认可见）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py reply \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
  --me <自己用户名> --body-file /tmp/reply.md
```

正文（你撰写，写入 `/tmp/reply.md`）结构示例：

```markdown
[@评审者](https://gitcode.com/评审者) 感谢评审，意见已处理（commit <sha>）。

> 文件路径:行号 评审意见原文摘录（major/...）

已处理：<具体改动说明>。
```

#### 5.2 发表行内评审意见（review，绑定文件:行号）

作为评审者给 PR 提意见、且要让意见**挂在 diff 的具体代码行旁**时，用 `review`。脚本自动从 `files.json` 取 `diff_refs`(base/start/head sha) 拼 position，再 POST v4 discussions，无需手动取 sha：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py review \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
  --path <文件相对路径> --line <行号> \
  --body-file /tmp/review.md [--start-line <起始行号>] [--severity suggestion|warning]
```

- `--line`：评论锚定的（结束）行号，对应新代码（`new_line`）。
- `--start-line`：多行选择的起始行号；省略即单行评论。
- `--severity`：`suggestion`（默认）或 `warning`。
- 返回 `{posted, discussion_id, path, line}`。

#### 5.3 回复已有行内评论（reply-review，落在对应线程）

回复**别人发起的某条行内评论**、且要让回复**挂在那条行内评论的线程里**（而非另起独立评论）时，用 `reply-review`。先用 `get-reviews` 取目标评论的 `discussion_id`，再回复：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py reply-review \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
  --discussion-id <目标行内评论的 discussion_id> --body-file /tmp/reply.md
```

脚本经 v4 `discussions/<id>/notes` 回复后，用 v5 单条评论接口回查，返回 `{posted, note_id, discussion_id, in_thread}`。**`in_thread=true` 才表示回复确实落在该行内线程里**（GET discussion 接口不可用、v5 列表不收行内回复，故 `in_thread` 由单条接口核对 discussion_id 得出，是权威判据）。`in_thread=false`/`null` 说明没挂上（如对机器人评审），应改用 5.1 引用回复。

> 三者区别：`reply` 发**不绑定行**的独立评论（回复机器人评审/汇总）；`review` **新发起**绑定 diff 某行的行内评论（逐行提意见）；`reply-review` 把回复**挂进别人已有的行内评论线程**（顺着某条行内意见往下答）。

### 6. 删除 PR 评论

**重要**：只能删除自己创建的评论，或具有仓库管理权限。

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py delete-comment \
  --owner <parent_owner> --repo <parent_repo> --comment-id <COMMENT_ID>
```

返回 `{deleted, http_code}`。评论 ID 可从 `get-reviews` 输出中取。

### 7. 创建 PR 的正确流程

**关键**：源分支必须基于**源仓**的目标分支，确保 PR 只包含期望的变更。

fork 场景下需区分两个远程：
- **源仓远程**（通常是 `upstream`，指向 `parent.full_name`）：PR 要合入的仓库，基线应从这里拉。
- **个人 fork 远程**（通常是 `origin`）：自己的工作分支推送到这里。

```bash
# 0. 确认/添加/校正源仓远程，确保 upstream 确实指向源仓
upstream_url="https://gitcode.com/${parent_owner}/${parent_repo}.git"
if git remote get-url upstream >/dev/null 2>&1; then
  # 已存在 upstream：归一化后精确比对 owner/repo，避免基于错误仓库拉分支。
  # 归一化：去协议/主机、去结尾 .git，兼容 https://host/o/r(.git) 与 git@host:o/r(.git)
  cur=$(git remote get-url upstream)
  cur_path=$(echo "$cur" | sed -E 's#^[^:]+://[^/]+/##; s#^[^@]+@[^:]+:##; s#\.git$##')
  if [ "$cur_path" = "${parent_owner}/${parent_repo}" ]; then
    : # 已正确指向源仓
  else
    echo "WARN: upstream 当前指向 $cur, 修正为源仓"
    git remote set-url upstream "$upstream_url"
  fi
else
  git remote add upstream "$upstream_url"
fi

# 1. 从源仓拉取目标分支（默认 master）
git fetch upstream <目标分支>

# 2. 基于源仓的目标分支创建新分支
git checkout -b <新分支名> upstream/<目标分支>

# 3. Cherry-pick 需要的 commit
git cherry-pick <commit-sha>          # 单个 commit
# 或
git cherry-pick <sha1> <sha2>         # 多个 commit

# 4. 推送到个人 fork 远程（origin）
git push origin <新分支名> -u
```

> 仅当明确要在 fork 仓内部提 PR 时，才改用 `origin/<目标分支>` 作为基线。

> **推送后固定动作（每次向 PR 推送改动后都执行，按顺序）**：
> 1. **一律触发流水线**：`pr_ops.py trigger --pr N --owner O --repo R`。无条件执行，不按"改动是否影响 CI"主观判断——PR 合入要求最终 head 有一轮通过的流水线，且让触发与否取决于判断正是遗漏的来源。即便纯文档改动也触发。
> 2. **判断是否同步 PR 描述**：本次改动若使描述过时（新增文件/功能、改变实现方式、解决新评审、累积多块改动）→ 用 `pr_ops.py update-pr` 更新；纯小修通常无需。是否更新由你判断，接口调用由脚本完成。
> 3. **跟进流水线结果**：按第 12 节监控（脚本轮询 + 模型判断）。

> **提交前本地检查（强烈建议）**：本仓 `.pre-commit-config.yaml` 配了 `ruff`/`pylint`/`bandit`，能在 push 前拦截大部分云端 `codecheck` 类 Python 问题、减少流水线失败轮次。首次需 `pre-commit install`（`.git/hooks/` 不随仓库走，每次 clone 各自装一次）；之后每次 `git commit` 自动对改动文件检查。注意它**不完全等价云端 codecheck**——华为专有规则（G.LOG.02 用 logging、G.EDV.05 subprocess 绝对路径、G.ERR.11 避免函数内 sys.exit 等）pylint 不一定覆盖，仍以云端结果为准。

**示例：基于源仓 master 提交单个 commit**
```bash
git fetch upstream master
git checkout -b fix/gcc13-link-error upstream/master
git cherry-pick 4fbf3b183
git push origin fix/gcc13-link-error -u
```

### 8. 创建 PR

**目标仓库策略**：
- **当前仓库是 fork 时，PR 默认创建到源仓（`parent.full_name`）**，API 路径中的 `${owner}/${repo}` 使用源仓。
- `head` 使用 `当前fork的owner:分支名` 形式跨仓提交。

**目标分支策略**：
- **默认合入源仓的 `master` 分支**，除非用户明确要求合入其他分支（如 `develop`、`release/x.y`）。

**用脚本创建 PR**（以源仓 `cann/oam-tools`、fork owner `sinat_31531339` 为例）：

```bash
python3 .claude/skills/gitcode-pr/scripts/create_pr.py \
  --owner <parent_owner> --repo <parent_repo> \
  --title "docs: 优化文档描述(#32)" \
  --head "fork_owner:fix/issue-32-description" \
  --base master --body-file /tmp/pr_body.md
```

**参数说明**：
- `--title`: PR 标题（必填）
- `--head`: 源分支，格式 `fork_owner:branch`（必填，跨仓提交时使用 fork 仓 owner）
- `--base`: 目标分支，**默认为源仓的 `master`**，除非用户明确要求合入其他分支
- `--body-file`: PR 描述文件（按下方模板撰写后传入；避免命令行转义问题）

**关联 Issue（解决 issue 的 PR 必须做）**：

当 PR 是为了解决某个 issue 时，**必须将 PR 关联到对应 issue**，便于追溯。

- **标题**：以 `(#issue_number)` 结尾，如 `test: msprof UT 新增覆盖率(#108)`。
- **描述**：正文包含 `关联 Issue #issue_number`，并在 PR 右侧「关联 Issue」面板添加对应 issue 链接。
- **issue 关闭时机**：保持 issue 开启，由用户在 PR 合入后自行手动关闭。为此：描述里用纯文本 `关联 Issue #issue_number`（而非 `Closes`/`Fixes` 等触发自动关闭的关键字），「合并后关闭已关联的 Issue」复选框保持不勾选。
- **合并后**：保持 issue 开启不动；如需确认关联是否生效，查 issue 关联的 PR：

```bash
# 查 issue 关联的 PR（确认关联生效，但不关闭 issue）
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py issue-prs \
  --owner <parent_owner> --repo <parent_repo> --issue <ISSUE_NUMBER>
```

### 9. PR URL 格式

创建 PR 后，PR 的访问地址格式为（注意是 `/pull/` 而非 `/pulls/`）：

```
https://gitcode.com/${parent_owner}/${parent_repo}/pull/<PR_NUMBER>
```

> fork 场景下 PR 位于源仓，故用 `${parent_owner}/${parent_repo}`；仅 fork 内部 PR 才用 `${owner}/${repo}`。

**示例**：`https://gitcode.com/cann/ge/pull/1807`

### 10. 触发构建流水线

PR 创建后，通过在 PR 评论区发布 `compile`（纯文本，不带斜杠）触发流水线。**用脚本触发，不要现写 curl**——脚本已固化 v4 notes 优先、返回 `{id:null}` 自动回退 v5 的逻辑：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py trigger \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

返回 `{"triggered": true, "via": "v4"|"v5"}`。

**原理参考**（脚本内已实现，无需手动操作）：
- 触发指令必须是 `compile` 纯文本；`/build`、`/compile`（带斜杠）无效。
- 走 v4 `merge_requests/<PR>/notes` 让评论进入 PR 普通评论区被机器人监听；v4 返回 `{id:null}`（发长文本时可能发生）则回退 v5 `/pulls/<PR>/comments` 重发。
- fork 场景 PR 位于源仓，`--owner/--repo` 传源仓（即 `resolve-repo` 输出的 `parent_owner/parent_repo`）。

### 11. CLA 与审批门禁

PR 创建后 `cann-robot` 会自动评论检查 CLA 签署与审批进度：

- **CLA 未签署**：常见原因是 commit 使用了 Git 自动生成的邮箱（如 `user@hostname.local`）。需先[签署 CLA](https://clasign.osinfra.cn)，或将 `git config user.email` 改为已签署邮箱后 `git commit --amend --reset-author` 并强推，然后评论 `/check-cla` 复检。
- **审批门禁**：通常需 ≥2 人 `/lgtm` + ≥1 人 `/approve`，committer 可在评论区操作。

### 12. 后续跟进（监控 PR 状态）

**创建 PR 并触发流水线后，必须先询问用户选择监控方式**，再据此执行。轮询监控是长时间、低强度的等待型任务，却持续占用当前高能力 agent 的 token，故给出三种方式按成本/掌控权取舍：

> 请选择 PR 的后续监控方式：
> 1. **不监控** —— 不轮询，后续由你自主操作（查看流水线/评审、决定何时改代码）。适合你想自己掌控节奏。
> 2. **本 agent 监控** —— 由我（当前 agent）持续轮询 PR 状态（流水线 + 评审 + state），发现问题自动改码、回复、重新触发，直到合入或阻塞。一个 agent 全程闭环，但轮询会持续消耗我的 token。
> 3. **其他 agent 监控（推荐）** —— 我只负责改代码 + 回复评审意见；流水线触发与轮询交给一个 token 消耗较少的独立 agent（如 opencode 或其他你惯用的 agent）。把机械的等待型轮询交给廉价 agent、高能力 agent 只做需要判断力的事，**更省费用**，故推荐此项。我改完/回复完后写一份交接文件并提示你，**由你手动启动那个 agent**去读文件、触发并轮询。

根据用户选择执行下面对应分支。

#### 12-A 选项1：不监控

向用户给出 PR 链接、当前流水线触发状态，并说明后续可随时让我「继续监控 PR <号>」。结束本次跟进，不启动任何轮询。

#### 12-B 选项2：本 agent 监控

PR 创建并触发流水线后，需**轮询监控** PR 状态直到合入或需要人工介入。每轮必须检查**三件事**：①流水线结果（cann-robot 评论）②人类评审意见（非 robot、非自己的评论）③PR `state`。三者每轮都要查；人类评审意见可能在流水线通过后、甚至分多轮陆续提出，因此持续轮询期间每轮都要重新拉取评审意见，而非只查一次。

**全程只用一个监控**：监控的对象是 **PR 本身**（按 PR 号持续盯它的状态、最新流水线结果与新评审），不绑定某一次 commit。推送新 commit、重新触发流水线后，**复用同一个监控**继续跟进，不要为每个 commit 另起新监控。每轮基于当前 `head` 的最新结果判断，直到 PR `merged`/`closed` 或出现需人工介入的阻塞时，该监控才结束。

**所有读取/回复操作都调脚本拿 JSON，不要现写 curl/jq**（脚本已固化 per_page=100、终态筛选、引用回复等踩坑逻辑）。先用 `resolve-repo` 拿到 `parent_owner/parent_repo`，下文 `--owner/--repo` 均传这两个值。

```bash
# 查 PR 状态（state: open/merged/closed）
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-state \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

- `state` 为 `merged` → 已合入，结束跟进。
- `state` 为 `closed`（未合入）→ 被关闭，停止并向用户说明。
- `state` 为 `open` → 按下面两步检查，未闭环则等待一轮后再查。

#### 12.1 流水线：未通过则查因、修复、重新触发

构建/门禁结果由 `cann-robot` 在评论区回报。但 `cann-robot` 还会发布 CLA、审批进度、label notification、「流水线任务触发成功」等**非结果**评论，不能取最后一条当结果。**用脚本取完成结果，已固化"只认含任务表与终态(SUCCESS/FAILED/WARNING)、排除触发成功"的筛选**：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-pipeline \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

返回 `{has_result, all_success, tasks, failed_tasks, created_at}`。判断：
- `has_result=false` → 流水线仍在跑，**继续等待**，不要据此判断状态。
- `has_result=true && all_success=true` → 流水线通过，进入 13.2 看评审意见。
- `has_result=true && all_success=false` → 看 `failed_tasks`：含 `FAILED`/`FAILURE`/`ERROR` 为真失败；仅 `WARNING` 通常不阻断合入，由你结合任务名判断是否需处理。

真失败时**必须**：
  1. 从失败日志/评论定位**根因**（编译错误、UT 失败、门禁未过等）。
  2. 在本地分支**修复**，提交并推送到 PR 源分支（`git push origin <branch>`）。
  3. 执行**推送后固定动作**（见第 8 节）：一律 `pr_ops.py trigger` 触发 → 判断是否 update-pr → 跟进。
  4. 回到 12.1 继续轮询，直到流水线通过。

> **每次修改并推送后，判断是否需同步更新 PR 描述**（见第 12.4 节）。新增文件/功能、改变实现方式、解决新的评审问题时，描述应随之更新；纯 bugfix/格式调整通常无需改。

**codecheck / precommit 门禁专项**：这两项的"通过与否"结论可脚本化获取——

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-codecheck \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo>
```

返回 `{codecheck_pass, codecheck_result, precommit_result, commit_id, detail_url}`。`commit_id` 可确认结论对应哪次提交。但**逐条告警明细无法脚本化**：明细在 `detail_url`（openlibing 看板）需登录查看，有 WAF 拦截程序化访问，且严禁把 token 发往该第三方域名——明细只能**由用户在浏览器登录后导出 xlsx**，再用 Python `zipfile` 解析（`xl/sharedStrings.xml` + `xl/worksheets/sheet1.xml`）。codecheck 是 Python 增量检查，编码须守仓库规范（print→logging、避免函数内 sys.exit、subprocess 用绝对路径、返回值一致、推导式不超两子句等）。

#### 12.2 评审意见：标准处理流程

**第 1 步：拉取全部评审意见**

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py get-reviews \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> --me <自己用户名>
```

返回 `{count, reviews:[{discussion_id, comment_type, user, created_at, body}]}`。

**第 2 步：对每条意见，先审视再决定**（不无脑照改）：
- 合理且应采纳 → 改码。
- 不认同或有更优方案 → 在回复里说明理由与替代方案。
- 疑问/澄清类 → 回复解答，无需改码。

判断依据参考 `superpowers:receiving-code-review`：先理解意图、技术上核实，再决定采纳与否，而非表演式同意或盲目实现。

**第 3 步：逐条回复——按 `comment_type` 选对子命令，每条都要回**：

| `comment_type` | 含义 | 回复方式 |
|----------------|------|----------|
| `diff_comment` | 绑定 `文件:行号` 的行内意见 | `reply-review --discussion-id <该条 did>` 逐条挂进对应行内线程；回查 `in_thread=true` 才算成功 |
| `pr_comment`（有实质内容） | 整轮总结意见 | `reply` 引用回复（`@评审者` + 引用块逐条摘录 + 处理说明） |
| `pr_comment` 为 `/lgtm`、`/approve` | 门禁指令 | 无需回复 |

逐条行内回复（`get-reviews` 输出里每条 `diff_comment` 的 `discussion_id`）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py reply-review \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
  --discussion-id <该行内意见的 discussion_id> --body-file /tmp/r.md
```

总结意见的引用回复见第 5.1 节。

> 覆盖性要求：`get-reviews` 返回的每条意见（除 `/lgtm`-`/approve`）都要有对应回复——逐条遍历 reviews，按 `comment_type` 各走对应子命令，行内与总结均覆盖。

**第 4 步：改码并推送后**，执行第 8 节**推送后固定动作**（一律 trigger 触发 → 判断 update-pr → 跟进），回到 12.1 轮询。

#### 12.3 闭环条件

持续轮询直到满足其一：
- `state=merged`（流水线通过 + 评审通过 + 门禁满足，通常 `cann-robot` 自动合入）→ 完成。
- `state=closed` 或出现需用户决策的阻塞（如 CLA 无法自动解决、评审分歧）→ 停止并向用户汇报。

#### 12.4 同步更新 PR 描述（多轮修改后）

PR 创建后经多轮修改（修流水线、采纳评审、新增文件/功能），初版描述会逐渐与实际内容脱节。**每轮修改推送后，判断 PR 描述是否已过时**：
- **应更新**：新增了文件/功能、改变了实现方式、解决了新的评审问题、累积了多块改动。
- **通常无需**：纯 bugfix、格式调整、不改变描述所述范围的小修。

是否更新、更新成什么由你（模型）据改动判断并撰写；写好新描述后用脚本调接口更新（PATCH，只改传入字段）：

```bash
python3 .claude/skills/gitcode-pr/scripts/pr_ops.py update-pr \
  --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> --body-file /tmp/pr_body.md
```

返回 `{updated, pr, fields}`。仅传 `--body/--body-file` 改描述；需改标题再加 `--title`（不传则不动）。描述应继续遵循仓库模板 `.gitcode/PULL_REQUEST_TEMPLATE.zh-CN.md` 的结构。

#### 12-C 选项3：脚本轮询 + 模型监听结果（推荐，省 token）

把"机械轮询等待"交给确定性脚本 `poll_pipeline.sh`，本 agent 只在脚本产出结果时被唤醒、做需要判断力的事（定位根因、改码、撰写回复）。脚本替代了原先"另起一个低成本 agent 轮询"的角色——无需常驻第二个 agent 进程，且天然支持**多轮循环**。

**单轮流程**：

1. **后台启动轮询脚本**（写 `.gitcode-handoff/result-<PR>.json`，到出完成结果或 merged/closed 即退出）：

   ```bash
   bash .claude/skills/gitcode-pr/scripts/poll_pipeline.sh \
     --pr <PR_NUMBER> --owner <parent_owner> --repo <parent_repo> \
     --interval 120 --max-wait 3600 &
   ```

2. **用 Monitor 监听结果文件**，脚本写出 `result-<PR>.json` 即唤醒本 agent，无需自己 sleep 轮询。

3. **读 result 判断**（脚本输出 `{state, has_result, pipeline_pass, failed_tasks, timeout}`）：
   - `state=merged` → 完成。
   - `state=closed` → 被关闭，向用户汇报。
   - `pipeline_pass=true` → 流水线通过，按 13.2 取评审意见、回复。
   - `pipeline_pass=false`（真失败）→ 按 13.1 定位根因 → 改码 → `git push` → `pr_ops.py reply` 回复评审 → `pr_ops.py trigger` 重新触发 → **回到第 1 步重起一轮 poll**（多轮循环）。
   - `timeout=true` → 超时仍无结果，向用户汇报由人工查看。

**多轮循环**：失败修复后重起 poll 脚本即进入下一轮，本 agent 仍只在每轮结果就绪时被唤醒，机械等待全程在脚本里，不消耗模型 token。

**职责边界**：脚本做轮询/取结果/触发/回复的 API 调用（确定性）；本 agent 只做定位根因、改代码、判断评审是否采纳、撰写回复正文（需判断力）。

**可选：跨独立 agent 交接**。若确需把轮询交给另一台机器/另一个独立 agent（而非本地脚本），可改写交接文件 `.gitcode-handoff/pipeline-<PR>.json`（含 pr/owner/repo/branch/head_sha），由该 agent 读取后调用同一套 `pr_ops.py` 执行；此为可选路径，默认用上面的本地脚本 + Monitor 即可。

---

## PR 代码审查

当用户说"检视 PR"、"审查 PR"、"review PR"、"给 PR 提意见"时触发。

### 执行步骤

1. **读取 commands/review.md** - 使用 Read 工具获取完整审查流程

2. **执行 review.md 中的审查流程**：
   - 步骤 1: 前置检查（PR 状态、草稿、是否已审查）
   - 步骤 2: 获取项目规范上下文
   - 步骤 3: 获取 PR 变更摘要
   - 步骤 4: 代码审查（Bug 扫描、规范合规性）
   - 步骤 5: 验证问题
   - 步骤 6: 过滤问题
   - 步骤 7: 输出审查摘要
   - 步骤 8: 准备评论列表（仅当提供 `--comment` 时）
   - 步骤 9: 发布行内评论（仅当提供 `--comment` 时）

**注意**：review.md 中包含每个步骤的详细说明和 API 示例。

---

## 输出格式

### 评论列表格式

获取 PR 评论后，使用以下格式输出：

```markdown
# PR 评论摘要

## 总体统计
- 讨论数量: X
- 行内评论: Y
- 已解决评论: Z

## 行内评论详情

### 1. 文件路径 - 第 N 行

**评论内容**: ...
**评论者**: @username
**时间**: YYYY-MM-DD HH:mm
**状态**: 未解决/已解决

**代码片段**:
```cpp
// 被评论的代码行
```

---

## PR 标题格式

遵循 Conventional Commits 规范：

```
<type>: <描述>(#issue_id)
```

**类型**：

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码风格 |
| `refactor` | 重构 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具 |

**示例**：
- `docs: 优化docs/api/README.md中的ge命名空间描述(#32)`
- `fix: 修复三库json下载安装问题`
- `feat: 添加operator注册V2接口支持(#45)`

---

## PR 描述模板

创建 PR 时使用以下模板格式化描述。

**重要**：
- **变更类型**：根据实际变更内容，将对应选项的 `[ ]` 改为 `[x]` 勾选
- **核对清单**：提交 PR 前所有项都应满足，默认全部勾选 `[x]`
- **从 `## 描述` 开始**：PR body 首个标题即 `## 描述`（PR 页面已有标题栏，无需再加 `# Pull Request` 顶级标题）

```markdown
## 描述
<!-- 根据代码变更内容填写描述 -->

## 变更类型
请选择本次引入的变更类型（勾选对应项）：
- [ ] 🐛 Bug 修复
- [ ] ✨ 新功能
- [ ] 💄 代码风格更新（格式化，局部变量）
- [ ] ♻️ 重构（既不修复错误也不增加功能的代码变动）
- [ ] 📦 构建过程或辅助工具的变动
- [ ] 📝 文档内容更新

## 关联的Issue
<!-- 在 PR 右侧「关联 Issue」面板添加链接；「合并后关闭已关联的 Issue」保持不勾选，issue 由用户在合入后手动关闭。 -->
关联 Issue #<issue_number>

## 如何测试
描述测试此变更的步骤和前提条件：

## 核对清单
- [ ] 我的代码遵循了项目的代码风格
- [ ] 我已对代码进行了自测
- [ ] 我已更新了相关的文档
- [ ] 我在标题中使用了合适的类型标签（如：`feat:`, `fix:`）
- [ ] 我已经详细阅读了贡献指南（CONTRIBUTING.md）

## 其他信息
在此添加任何其他关于本次 PR 的说明。
```

---

## Resources

### references/gitcode_api.md

GitCode API 完整参考文档，用于：
- 了解 API 参数格式
- 查看响应结构
- 排查 API 调用问题
