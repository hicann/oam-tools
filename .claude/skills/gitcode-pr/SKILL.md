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

当当前仓库是 fork 仓库时，需要查询其 fork 的原仓库作为 PR 目标仓库：

```bash
# 查询仓库信息获取 fork 来源
curl -s -H "Authorization: Bearer $GITCODE_API_TOKEN" \
  "https://api.gitcode.com/api/v5/repos/${owner}/${repo}" | \
  jq -r '
    if .fork then
      "原仓库: " + .parent.full_name + "\n" +
      "原仓库URL: " + .parent.html_url + "\n" +
      "目标分支: " + .parent.default_branch
    else
      "这不是一个 fork 仓库，直接使用当前仓库"
    end
  '
```

**初始化目标仓库变量（后续所有 API 调用都用这组变量）**：

```bash
# 查询当前仓信息（保存响应与 HTTP 状态，便于校验）
repo_resp=$(curl -s -w $'\n%{http_code}' -H "Authorization: Bearer $GITCODE_API_TOKEN" \
  "https://api.gitcode.com/api/v5/repos/${owner}/${repo}")
http_code="${repo_resp##*$'\n'}"
repo_json="${repo_resp%$'\n'*}"

if [[ "$http_code" != "200" ]]; then
  echo "ERROR: 查询仓库信息失败 (HTTP $http_code)，无法确定目标仓，终止" >&2
  return 1 2>/dev/null || exit 1
fi

# 解析 fork 字段；jq 失败或字段缺失则报错退出，不静默回退
fork_flag=$(printf '%s' "$repo_json" | jq -r '.fork')
if [[ "$fork_flag" != "true" && "$fork_flag" != "false" ]]; then
  echo "ERROR: 解析 fork 字段失败（响应异常），终止" >&2
  return 1 2>/dev/null || exit 1
fi

if [[ "$fork_flag" == "true" ]]; then
  # fork：PR 目标为源仓
  parent_full=$(printf '%s' "$repo_json" | jq -r '.parent.full_name')
  if [[ -z "$parent_full" || "$parent_full" == "null" ]]; then
    echo "ERROR: fork=true 但缺少 parent.full_name，无法确定源仓，终止" >&2
    return 1 2>/dev/null || exit 1
  fi
  parent_owner="${parent_full%%/*}"
  parent_repo="${parent_full##*/}"
else
  # 明确 fork=false：目标即当前仓
  parent_owner="$owner"
  parent_repo="$repo"
fi

# 目标仓库的 v4 项目路径（URL 编码），用于 merge_requests 相关查询
parent_encoded_repo=$(printf '%s' "${parent_owner}/${parent_repo}" | jq -sRr @uri)

echo "目标仓: ${parent_owner}/${parent_repo} (encoded: ${parent_encoded_repo})"
```

**后续约定**：
- 创建 PR / 查 PR 状态（v5）用 `${parent_owner}/${parent_repo}`。
- merge_requests 的讨论、评论、notes（v4）用 `${parent_encoded_repo}`。
- 仅在操作**当前 fork 仓自身**时才用 `${owner}/${repo}` 与 `${encoded_repo}`。
- 凡命令片段用到 `${parent_*}` 变量，先在本节完成初始化再引用，确保片段可直接跑通。

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

### 3. 获取 PR 评论和讨论

#### 获取 PR 讨论列表（包含行内评论）

GitCode 使用 GitLab API v4 格式获取 PR 讨论和评论：

```bash
# 获取 PR 的所有讨论（包括行内评论）
curl -s -H "PRIVATE-TOKEN: $GITCODE_API_TOKEN" \
  "https://api.gitcode.com/api/v4/projects/${parent_encoded_repo}/merge_requests/<PR_NUMBER>/discussions"
```

**关键说明**：
- 认证头使用 `PRIVATE-TOKEN:`（不是 `Authorization: Bearer`）
- 项目路径需要 URL 编码：`${encoded_repo}` = `owner%2Frepo`
- 使用 `merge_requests` 而不是 `pulls`
- 使用 GitLab API v4: `/api/v4/projects/`

#### 解析讨论数据

返回的讨论数据包含以下关键字段：

| 字段 | 说明 |
|------|------|
| `notes[].type` | 评论类型：`DiffNote` 表示行内评论，`DiscussionNote` 表示普通讨论 |
| `notes[].body` | 评论内容 |
| `notes[].author` | 评论作者信息 |
| `notes[].position` | 行内评论的位置信息 |
| `notes[].diff_file` | 被评论的文件路径 |
| `notes[].new_line` | 新代码行号 |
| `notes[].content` | 被评论的具体代码行内容 |
| `notes[].resolved` | 评论是否已解决 |
| `notes[].created_at` | 评论创建时间 |

**行内评论的 position 字段结构**：
```json
{
  "base_sha": "base提交SHA",
  "start_sha": "start提交SHA",
  "head_sha": "head提交SHA",
  "old_path": "旧文件路径",
  "new_path": "新文件路径",
  "old_line": null,
  "new_line": 46,
  "diff_id": 5664724
}
```

### 4. 获取 PR 文件变更

```bash
# 基本查询
curl -s -H "PRIVATE-TOKEN: $GITCODE_API_TOKEN" \
  "https://api.gitcode.com/api/v4/projects/${parent_encoded_repo}/merge_requests/<PR_NUMBER>/changes"

# 每页 100 条
curl -s -H "PRIVATE-TOKEN: $GITCODE_API_TOKEN" \
  "https://api.gitcode.com/api/v4/projects/${parent_encoded_repo}/merge_requests/<PR_NUMBER>/changes?per_page=100"
```

### 5. 提交行内评论（支持多行选择）

#### 创建新的 Discussion（推荐）

```bash
curl -s -X POST \
  -H "PRIVATE-TOKEN: $GITCODE_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.gitcode.com/api/v4/projects/${parent_encoded_repo}/merge_requests/<PR_NUMBER>/discussions" \
  -d '{
    "repoId": "'"${parent_encoded_repo}"'",
    "iid": <PR_NUMBER>,
    "body": "评论内容",
    "line_types": "new",
    "position": {
      "base_sha": "<base_commit_sha>",
      "start_sha": "<start_commit_sha>",
      "head_sha": "<head_commit_sha>",
      "position_type": "text",
      "old_path": "文件路径",
      "new_path": "文件路径",
      "old_line": null,
      "new_line": <结束行号>,
      "start_old_line": null,
      "start_new_line": <起始行号>,
      "ignore_whitespace_change": false
    },
    "assignee_id": <用户ID>,
    "proposer_id": <用户ID>,
    "severity": "suggestion"
  }'
```

**多行选择说明**：
- `start_new_line`: 选中的起始行号（多行选择时设置）
- `new_line`: 选中的结束行号
- 单行评论时，`start_new_line` 和 `new_line` 设置为相同值

**参数说明**：

| 参数 | 说明 | 必需 |
|------|------|------|
| `body` | 评论内容 | ✅ |
| `line_types` | `"new"` 选择新代码（右侧），`"old"` 选择旧代码（左侧） | ✅ |
| `position.base_sha` | base 提交 SHA | ✅ |
| `position.start_sha` | start 提交 SHA | ✅ |
| `position.head_sha` | head 提交 SHA | ✅ |
| `position.new_path` | 文件相对路径 | ✅ |
| `position.new_line` | 结束行号 | ✅ |
| `position.start_new_line` | 起始行号（多行选择） | 多行时 |
| `severity` | 严重程度：`suggestion`、`warning` | ❌ |

#### 回复评审意见（引用回复，不要依赖"挂线程"）

**实测结论（重要，避免踩坑）**：GitCode 对机器人评审（`cann-robot` / `cann-tool-pr-reviewer`）**无法真正嵌套回复**。即使调用 `discussions/<discussion_id>/notes` 且返回的 `discussion_id` 与原评论一致，该回复**不会**出现在评审意见线程下，也不会出现在 v5 评论列表里——它实际另起了一条自带新 `discussion_id` 的独立评论。**不要用"返回 discussion_id 一致"判断回复成功，必须回 v5 列表（`per_page=100`）核对回复是否真的可见、归属是否正确。**

因此对评审意见统一采用**引用回复**：发一条普通 PR 评论，正文 `@评审者` 并用引用块（`>`）**逐条摘录**每条意见的 `文件:行号` + 原文，紧跟该意见的处理说明（已采纳/commit、替代方案、或不成立的理由），做到一一对应。这样虽不嵌套，但内容上明确对应到每条评审意见。

```bash
# 用 v5 评论接口发引用回复，确保进入 PR 普通评论区
curl -s -X POST -H "Content-Type: application/json" -H "Accept: application/json" \
  "https://api.gitcode.com/api/v5/repos/${parent_owner}/${parent_repo}/pulls/<PR_NUMBER>/comments?access_token=$GITCODE_API_TOKEN" \
  -d "{\"body\":$(jq -Rs . <<<"$body")}"
```

引用回复正文结构示例：

```markdown
[@评审者](https://gitcode.com/评审者) 感谢评审，意见已处理（commit <sha>）。

> 文件路径:行号 评审意见原文摘录（major/...）

已处理：<具体改动说明>。
```

发送后**必须**用 v5 列表（`per_page=100`）确认该评论已可见，再继续后续动作。

### 6. 提交普通评论

```bash
curl -s -X POST \
  -H "PRIVATE-TOKEN: $GITCODE_API_TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.gitcode.com/api/v4/projects/${parent_encoded_repo}/merge_requests/<PR_NUMBER>/notes" \
  -d '{
    "body": "评论内容"
  }'
```

### 7. 删除 PR 评论

当用户需要删除 PR 中的评论时使用此功能。

**重要**：只能删除自己创建的评论，或具有仓库管理权限。

```bash
# 获取评论 ID
curl -s -H "PRIVATE-TOKEN: $GITCODE_API_TOKEN" \
  "https://api.gitcode.com/api/v4/projects/${parent_encoded_repo}/merge_requests/<PR_NUMBER>/notes" | \
  jq '.[] | {id: .id, author: .author.username, body: .body}'

# 删除评论（fork 场景 PR 评论属源仓，故用 ${parent_owner}/${parent_repo}；仅 fork 内部 PR 才用 ${owner}/${repo}）
curl -s -X DELETE \
  "https://api.gitcode.com/api/v5/repos/${parent_owner}/${parent_repo}/pulls/comments/<COMMENT_ID>?access_token=$GITCODE_API_TOKEN"
```

详细 API 参数、响应码和权限说明请参考 `references/gitcode_api.md` 的「删除 PR 评论」章节。

### 8. 创建 PR 的正确流程

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

**示例：基于源仓 master 提交单个 commit**
```bash
git fetch upstream master
git checkout -b fix/gcc13-link-error upstream/master
git cherry-pick 4fbf3b183
git push origin fix/gcc13-link-error -u
```

### 9. 创建 PR

**目标仓库策略**：
- **当前仓库是 fork 时，PR 默认创建到源仓（`parent.full_name`）**，API 路径中的 `${owner}/${repo}` 使用源仓。
- `head` 使用 `当前fork的owner:分支名` 形式跨仓提交。

**目标分支策略**：
- **默认合入源仓的 `master` 分支**，除非用户明确要求合入其他分支（如 `develop`、`release/x.y`）。

使用 GitCode API 创建 PR（以源仓 `cann/oam-tools`、fork owner `sinat_31531339` 为例）：

```bash
curl -s -X POST "https://gitcode.com/api/v5/repos/${parent_owner}/${parent_repo}/pulls" \
  -H "Authorization: Bearer $GITCODE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "docs: 优化文档描述(#32)",
    "head": "fork_owner:fix/issue-32-description",
    "base": "master",
    "body": "PR描述内容（见下方模板）"
  }'
```

**参数说明**：
- `title`: PR 标题（必填）
- `head`: 源分支，格式 `fork_owner:branch`（必填，跨仓提交时使用 fork 仓 owner）
- `base`: 目标分支，**默认为源仓的 `master`**，除非用户明确要求合入其他分支
- `body`: PR 描述（Markdown 格式）

**关联 Issue（解决 issue 的 PR 必须做）**：

当 PR 是为了解决某个 issue 时，**必须将 PR 关联到对应 issue**，便于追溯。

- **标题**：以 `(#issue_number)` 结尾，如 `test: msprof UT 新增覆盖率(#108)`。
- **描述**：正文包含 `关联 Issue #issue_number`，并在 PR 右侧「关联 Issue」面板添加对应 issue 链接。
- **不要自动关闭 issue**：**不要**勾选「合并后关闭已关联的 Issue」，也不要用 `Closes`/`Fixes` 等会触发自动关闭的关键字。**issue 由用户在 PR 合入后自行手动关闭。**
- **合并后**：不主动关闭 issue。如需确认关联是否生效，可查 issue 关联的 PR：

```bash
# 查 issue 关联的 PR（确认关联生效，但不关闭 issue）
curl -s -H "Authorization: Bearer $GITCODE_API_TOKEN" \
  "https://gitcode.com/api/v5/repos/${parent_owner}/${parent_repo}/issues/<ISSUE_NUMBER>/pull_requests" \
  | jq -r '.[] | "PR #\(.number) [\(.state)] \(.title)"'
```

### 10. PR URL 格式

创建 PR 后，PR 的访问地址格式为（注意是 `/pull/` 而非 `/pulls/`）：

```
https://gitcode.com/${parent_owner}/${parent_repo}/pull/<PR_NUMBER>
```

> fork 场景下 PR 位于源仓，故用 `${parent_owner}/${parent_repo}`；仅 fork 内部 PR 才用 `${owner}/${repo}`。

**示例**：`https://gitcode.com/cann/ge/pull/1807`

### 11. 触发构建流水线

PR 创建后，通过在 PR 评论区发布指令触发构建流水线。

**关键：触发指令为 `compile`（纯文本，不带斜杠 `/`）。**

复用本 skill 既有的「提交普通评论」接口（v4 notes），确保 `compile` 进入 PR 普通评论区被机器人监听。fork 场景下 PR 位于源仓，故使用 `${parent_encoded_repo}`：

```bash
curl -s -X POST \
  "https://api.gitcode.com/api/v4/projects/${parent_encoded_repo}/merge_requests/<PR_NUMBER>/notes" \
  -H "PRIVATE-TOKEN: $GITCODE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":"compile"}'
```

> 注意：`/build`、`/compile`（带斜杠）等指令无效，不会触发流水线。

评论与触发流水线统一使用上述 v4 notes 接口，不混用 v4/v5。发出评论后通过拉取评论列表确认其已出现，再继续后续动作；若返回 `{id:null}` 或列表中查不到（v4 notes 发长文本时可能发生），改用 v5 `/pulls/<PR_NUMBER>/comments` 接口重发。

### 12. CLA 与审批门禁

PR 创建后 `cann-robot` 会自动评论检查 CLA 签署与审批进度：

- **CLA 未签署**：常见原因是 commit 使用了 Git 自动生成的邮箱（如 `user@hostname.local`）。需先[签署 CLA](https://clasign.osinfra.cn)，或将 `git config user.email` 改为已签署邮箱后 `git commit --amend --reset-author` 并强推，然后评论 `/check-cla` 复检。
- **审批门禁**：通常需 ≥2 人 `/lgtm` + ≥1 人 `/approve`，committer 可在评论区操作。

### 13. 后续跟进（轮询监控 PR 状态）

PR 创建并触发流水线后，需**轮询监控** PR 状态直到合入或需要人工介入。每轮必须检查**三件事**：①流水线结果（cann-robot 评论）②人类评审意见（非 robot、非自己的评论）③PR `state`。三者每轮都要查；人类评审意见可能在流水线通过后、甚至分多轮陆续提出，因此持续轮询期间每轮都要重新拉取评审意见，而非只查一次。

**全程只用一个监控**：监控的对象是 **PR 本身**（按 PR 号持续盯它的状态、最新流水线结果与新评审），不绑定某一次 commit。推送新 commit、重新触发流水线后，**复用同一个监控**继续跟进，不要为每个 commit 另起新监控。每轮基于当前 `head` 的最新结果判断，直到 PR `merged`/`closed` 或出现需人工介入的阻塞时，该监控才结束。

```bash
# 轮询查 PR 状态（state: open/merged/closed）
curl -s -H "Authorization: Bearer $GITCODE_API_TOKEN" \
  "https://gitcode.com/api/v5/repos/${parent_owner}/${parent_repo}/pulls/<PR_NUMBER>" \
  | jq '{state, merged_at}'
```

- `state` 为 `merged` → 已合入，结束跟进。
- `state` 为 `closed`（未合入）→ 被关闭，停止并向用户说明。
- `state` 为 `open` → 按下面两步检查，未闭环则等待一轮后再查。

#### 13.1 流水线：未通过则查因、修复、重新触发

构建/门禁结果由 `cann-robot` 在评论区回报。但 `cann-robot` 还会发布 CLA、审批进度、label notification、「流水线任务触发成功」等**非结果**评论，**不能直接取它的最后一条评论当流水线结果**，否则会把触发提示等误判为结果。应只筛选**包含完成结果特征**的评论——任务状态表 + `SUCCESS`/`FAILED`/`WARNING` 等终态，且优先取最新一条：

```bash
# 必须带 per_page=100，v5 默认每页仅 20 条，会漏看最新结果
# 只认含 CI 任务表与终态(SUCCESS/FAILED/WARNING)的"完成结果"评论，排除"触发成功"等噪声
curl -s "https://api.gitcode.com/api/v5/repos/${parent_owner}/${parent_repo}/pulls/<PR_NUMBER>/comments?per_page=100&access_token=$GITCODE_API_TOKEN" \
  | jq -r '[.[] | select(.user.login=="cann-robot")
            | select(.body|test("SUCCESS|FAILED|FAILURE|WARNING"))
            | select(.body|test("触发成功")|not)]
           | sort_by(.created_at) | last | "[\(.created_at)] \(.body)"'
```

判断时：
- 若只看到「流水线任务触发成功」而**没有**带终态的完成结果评论 → 流水线仍在跑，**继续等待**，不要据此判断状态。
- 出现完成结果后，看任务表里是否有非 `SUCCESS` 的任务。

- **流水线通过**（完成结果中所有任务 `SUCCESS`） → 进入 13.2 看评审意见。
- **流水线未通过**（出现 `FAILED`/`FAILURE`/`ERROR` 等） → **必须**：
  1. 从失败日志/评论定位**根因**（编译错误、UT 失败、门禁未过等）。
  2. 在本地分支**修复**，提交并推送到 PR 源分支（`git push origin <branch>`）。
  3. **重新触发流水线**：在 PR 评论区发布 `compile`（纯文本，见第 11 节）。
  4. 回到 13.1 继续轮询，直到流水线通过。

#### 13.2 评审意见：审视后决定是否修改

```bash
# 拉取所有评论，关注非 cann-robot/非自己的人类评审
# 关键：必须带 per_page=100，v5 默认每页仅 20 条，会漏看新评审与新流水线结果
curl -s "https://api.gitcode.com/api/v5/repos/${parent_owner}/${parent_repo}/pulls/<PR_NUMBER>/comments?per_page=100&access_token=$GITCODE_API_TOKEN" \
  | jq -r '.[] | select(.user.login!="cann-robot") | "[\(.created_at)] \(.comment_type) @\(.user.login // .user): \(.body|gsub("\n";" ")|.[0:80])"'
```

对每条评审意见**审视后再决定**，不要无脑照改：
- **合理且应采纳** → 在本地修改、推送、并用引用回复说明已处理（见第 5 节）。
- **不认同或有更优方案** → 在评论区**说明理由**与替代方案，与评审者达成一致后再定。
- **疑问/澄清类** → 回复解答，无需改码。

> 判断依据参考 `superpowers:receiving-code-review`：先理解意图、技术上核实，再决定采纳与否，而非表演式同意或盲目实现。

处理每条意见的步骤：先读对应代码核实意见是否成立，再决定采纳、采用替代方案或回复说明不成立（如上）。**对机器人评审无法嵌套回复，统一用引用回复**（见第 5 节）：发一条 `@评审者` 的普通评论，用引用块逐条摘录每条意见的 `文件:行号` + 原文并紧跟处理说明，做到内容一一对应。

**评审者通常同时留下两类评论，回复时两类意见都要覆盖，不能因为是 `pr_comment` 就漏掉**：
- **A 类：逐行的行内评论**（`comment_type=diff_comment`）——针对某个 `文件:行号` 的具体问题。
- **B 类：整轮的总结评论**（`comment_type=pr_comment`，如「结论：有问题，下面几处建议先处理…」）——把本轮所有 A 类意见汇总成一条。

A、B 内容通常一一对应（B 是 A 的汇总）。引用回复时把本轮 A 类逐条覆盖即等于回应了 B。**唯一无需回复的 `pr_comment` 是 `/lgtm`、`/approve` 这类门禁指令评论**——其余有实质意见的评论都要在引用回复里覆盖，切勿把所有 `pr_comment` 一概当作无需回复。

修改后同样要 `compile` 重新触发流水线，并回到 13.1 轮询。

#### 13.3 闭环条件

持续轮询直到满足其一：
- `state=merged`（流水线通过 + 评审通过 + 门禁满足，通常 `cann-robot` 自动合入）→ 完成。
- `state=closed` 或出现需用户决策的阻塞（如 CLA 无法自动解决、评审分歧）→ 停止并向用户汇报。

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
- **不带一级标题**：PR body 从 `## 描述` 开始，**不要** `# Pull Request` 顶级标题（PR 页面已有标题栏，重复多余）

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
<!-- 在 PR 右侧「关联 Issue」面板添加链接，但不要勾选「合并后关闭已关联的 Issue」；issue 由用户在合入后手动关闭。 -->
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
