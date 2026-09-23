#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
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
"""
clean.py — Ascend NPU 日志清洗脚本

功能：
  - 去除冗余的 DEBUG 级别日志（可配置）
  - 提取关键错误/警告行
  - 统一时间戳格式
  - 去重重复行
  - 支持多日志来源合并并按时间排序

用法：
  python3 clean.py --input <log_file> --output <output_file>
  python3 clean.py --input-dir <dir> --output-dir <out_dir>
  python3 clean.py --input <log_file> --level ERROR --output <output_file>
"""

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime

# ===================== 配置 =====================
# 日志级别优先级（数值越小越详细）
LOG_LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "WARN": 2, "ERROR": 3, "FATAL": 4}

# 噪声行模式：匹配后会被过滤（DEBUG 心跳、定时轮询）
NOISE_PATTERNS = [
    r"\[DEBUG\].*heartbeat",
    r"\[DEBUG\].*polling",
    r"\[DEBUG\].*tick",
    r"^\s*$",  # 空行
]

# 关键字：包含这些词的行即使是 DEBUG 也保留
IMPORTANT_KEYWORDS = [
    "error", "fail", "exception", "crash", "oom", "timeout",
    "retcode", "assert", "panic", "killed",
]

# 时间戳正则（多种格式兼容）
TS_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[.,]\d+)"),
    re.compile(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{2}:\d{2}:\d{2}[.,]\d+)"),
]
CANN_TS_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2})-(\d{2}:\d{2}:\d{2})[.,](\d{3})(?:[.,](\d{3}))?"
)


# ===================== 工具函数 =====================

def parse_log_level(line: str) -> str:
    """从日志行中提取日志级别"""
    for level in LOG_LEVELS:
        if f"[{level}]" in line.upper() or f" {level} " in line.upper():
            return level
    return "INFO"  # 默认视为 INFO


def extract_timestamp(line: str) -> datetime | None:
    """提取日志行中的时间戳"""
    cann_match = CANN_TS_PATTERN.search(line)
    if cann_match:
        date_part, time_part, millis, micros = cann_match.groups()
        fraction = millis + (micros or "")
        try:
            return datetime.strptime(
                f"{date_part} {time_part}.{fraction}",
                "%Y-%m-%d %H:%M:%S.%f",
            )
        except ValueError:
            pass

    for pattern in TS_PATTERNS:
        m = pattern.search(line)
        if m:
            ts_str = m.group(1)
            for fmt in [
                "%Y-%m-%d %H:%M:%S,%f",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                "%H:%M:%S,%f",
                "%H:%M:%S.%f",
            ]:
                try:
                    return datetime.strptime(ts_str, fmt)
                except ValueError:
                    continue
    return None


def is_noise(line: str) -> bool:
    """判断是否为噪声行"""
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            # 即使命中噪声，若包含重要关键字则保留
            if any(kw in line.lower() for kw in IMPORTANT_KEYWORDS):
                return False
            return True
    return False


def clean_lines(lines: list[str], min_level: str = "INFO") -> list[str]:
    """
    清洗日志行列表。

    Args:
        lines: 原始日志行
        min_level: 最低保留级别（DEBUG/INFO/WARNING/ERROR/FATAL）

    Returns:
        清洗后的日志行
    """
    min_priority = LOG_LEVELS.get(min_level.upper(), 1)
    seen = set()
    result = []

    for line in lines:
        line = line.rstrip("\n")

        # 过滤空行（单独处理，不计入去重）
        if not line.strip():
            continue

        # 去重
        if line in seen:
            continue
        seen.add(line)

        # 噪声过滤
        if is_noise(line):
            continue

        # 日志级别过滤
        level = parse_log_level(line)
        if LOG_LEVELS.get(level, 1) < min_priority:
            # 即使低于最低级别，包含重要关键字的行也保留
            if not any(kw in line.lower() for kw in IMPORTANT_KEYWORDS):
                continue

        result.append(line)

    return result


def process_file(input_path: Path, output_path: Path, min_level: str = "INFO") -> int:
    """处理单个日志文件，返回保留的行数"""
    try:
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError as e:
        print(f"[ERROR] 无法读取 {input_path}: {e}", file=sys.stderr)
        return 0

    cleaned = clean_lines(lines, min_level)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned) + ("\n" if cleaned else ""))

    return len(cleaned)


# ===================== CLI =====================

def main():
    parser = argparse.ArgumentParser(
        description="Ascend NPU 日志清洗工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=Path, help="单个输入日志文件路径")
    group.add_argument("--input-dir", type=Path, help="批量输入目录（递归处理 *.log）")

    out_group = parser.add_mutually_exclusive_group()
    out_group.add_argument("--output", type=Path, help="单文件输出路径")
    out_group.add_argument("--output-dir", type=Path, help="批量输出目录")

    parser.add_argument(
        "--level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "FATAL"],
        help="最低保留日志级别（默认：INFO）",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="将所有日志合并为单文件并按时间排序（配合 --output 使用）",
    )

    args = parser.parse_args()

    total_kept = 0

    if args.input:
        # 单文件模式
        output_path = args.output or args.input.with_suffix(".clean.log")
        kept = process_file(args.input, output_path, args.level)
        print(f"[INFO] {args.input} → {output_path}（保留 {kept} 行）")
        total_kept = kept

    elif args.input_dir:
        # 批量模式
        log_files = list(args.input_dir.rglob("*.log"))
        if not log_files:
            print(f"[WARN] 在 {args.input_dir} 中未找到 .log 文件", file=sys.stderr)
            sys.exit(0)

        output_dir = args.output_dir or args.input_dir.parent / (args.input_dir.name + "_cleaned")

        if args.merge and args.output:
            # 合并模式：读取所有文件、清洗、按时间戳排序后写入单文件
            all_lines = []
            for f in log_files:
                try:
                    with open(f, "r", encoding="utf-8", errors="replace") as fh:
                        all_lines.extend(fh.readlines())
                except OSError:
                    pass
            cleaned = clean_lines(all_lines, args.level)
            # 尝试按时间戳排序
            def sort_key(line):
                ts = extract_timestamp(line)
                return ts or datetime.min
            cleaned.sort(key=sort_key)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write("\n".join(cleaned) + "\n")
            print(f"[INFO] 合并完成 → {args.output}（保留 {len(cleaned)} 行）")
            total_kept = len(cleaned)
        else:
            for log_file in log_files:
                rel = log_file.relative_to(args.input_dir)
                out_path = output_dir / rel.with_suffix(".clean.log")
                kept = process_file(log_file, out_path, args.level)
                print(f"[INFO] {log_file} → {out_path}（保留 {kept} 行）")
                total_kept += kept

    print(f"[DONE] 共保留 {total_kept} 行日志")


if __name__ == "__main__":
    main()
