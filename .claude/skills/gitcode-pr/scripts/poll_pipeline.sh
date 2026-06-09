#!/bin/bash
# ----------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
#
# 流水线定时轮询脚本：替代"轮询 agent"角色。后台跑，单轮出结果即写
# result-<PR>.json 并退出，交大模型判断。复用 pr_ops.py，不自己写 curl。
#
# 用法：
#   bash poll_pipeline.sh --pr 299 --owner cann --repo oam-tools \
#       [--interval 120] [--max-wait 3600] [--out .gitcode-handoff/result-299.json]
#
# 退出后读 result 文件：
#   {state, has_result, pipeline_pass, failed_tasks, timeout, ts}
#   - pipeline_pass=true  → 流水线通过，模型可继续看评审/等合入
#   - pipeline_pass=false → 有非 SUCCESS 任务，模型据 failed_tasks 定位
#   - timeout=true        → 超过 max-wait 仍无完成结果，需人工查看
#   - state=merged/closed → PR 已终态

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PR_OPS="${SCRIPT_DIR}/pr_ops.py"

INTERVAL=120
MAX_WAIT=3600
OUT=""
PR=""; OWNER=""; REPO=""; SINCE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pr) PR="$2"; shift 2 ;;
        --owner) OWNER="$2"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        --max-wait) MAX_WAIT="$2"; shift 2 ;;
        --since) SINCE="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$PR" || -z "$OWNER" || -z "$REPO" ]]; then
    echo "ERROR: --pr --owner --repo 必填" >&2
    exit 1
fi

[[ -z "$OUT" ]] && OUT=".gitcode-handoff/result-${PR}.json"
mkdir -p "$(dirname "$OUT")"

write_result() {
    # $1=完整 JSON 字符串
    printf '%s\n' "$1" > "$OUT"
    echo "result written: $OUT"
    cat "$OUT"
}

ts() { date -u +%FT%TZ; }

elapsed=0
while true; do
    # ① PR 终态优先
    state_json=$(python3 "$PR_OPS" get-state --pr "$PR" --owner "$OWNER" --repo "$REPO")
    state=$(printf '%s' "$state_json" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("state",""))' 2>/dev/null)
    if [[ "$state" == "merged" || "$state" == "closed" ]]; then
        write_result "{\"state\":\"$state\",\"has_result\":true,\"pipeline_pass\":$([[ $state == merged ]] && echo true || echo false),\"final\":true,\"ts\":\"$(ts)\"}"
        exit 0
    fi

    # ② 流水线完成结果（带 --since 时只认本轮新结果）
    since_args=()
    [[ -n "$SINCE" ]] && since_args=(--since "$SINCE")
    pipe_json=$(python3 "$PR_OPS" get-pipeline --pr "$PR" --owner "$OWNER" --repo "$REPO" "${since_args[@]}")
    has_result=$(printf '%s' "$pipe_json" | python3 -c 'import sys,json;print(str(json.load(sys.stdin).get("has_result",False)).lower())' 2>/dev/null)
    if [[ "$has_result" == "true" ]]; then
        ppass=$(printf '%s' "$pipe_json" | python3 -c 'import sys,json;print(str(json.load(sys.stdin).get("pipeline_pass",False)).lower())' 2>/dev/null)
        failed=$(printf '%s' "$pipe_json" | python3 -c 'import sys,json;print(json.dumps(json.load(sys.stdin).get("failed_tasks",[]),ensure_ascii=False))' 2>/dev/null)
        warns=$(printf '%s' "$pipe_json" | python3 -c 'import sys,json;print(json.dumps(json.load(sys.stdin).get("warning_tasks",[]),ensure_ascii=False))' 2>/dev/null)
        write_result "{\"state\":\"$state\",\"has_result\":true,\"pipeline_pass\":$ppass,\"failed_tasks\":$failed,\"warning_tasks\":$warns,\"ts\":\"$(ts)\"}"
        exit 0
    fi

    # ③ 仍在跑：等待
    if [[ $elapsed -ge $MAX_WAIT ]]; then
        write_result "{\"state\":\"$state\",\"has_result\":false,\"timeout\":true,\"ts\":\"$(ts)\"}"
        exit 0
    fi
    echo "pipeline running, wait ${INTERVAL}s (elapsed ${elapsed}s/${MAX_WAIT}s)..."
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
done
