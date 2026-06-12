#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
"""generate_report.py 的静态 HTML 资源：CSS 样式与 JS 模板常量。

从 generate_report.py 分离，避免单文件过大；内容逐字节保持不变。
"""
HTML_CSS = '''
    <style>
    :root {
        --bg-primary: #1e1e1e;
        --bg-secondary: #252526;
        --bg-tertiary: #2d2d2d;
        --bg-hover: #2d2d2d;
        --text-primary: #d4d4d4;
        --text-secondary: #808080;
        --accent-blue: #4fc1ff;
        --accent-green: #6a9955;
        --accent-orange: #ce9178;
        --border-color: #3c3c3c;
        --button-bg: #0e639c;
        --button-hover: #1177bb;
        --tooltip-bg: #1e1e2e;
        --tooltip-border: #45475a;
    }
    [data-theme="dracula"] {
        --bg-primary: #282a36;
        --bg-secondary: #21222c;
        --bg-tertiary: #343746;
        --bg-hover: #44475a;
        --text-primary: #f8f8f2;
        --text-secondary: #6272a4;
        --accent-blue: #8be9fd;
        --accent-green: #50fa7b;
        --accent-orange: #ffb86c;
        --border-color: #44475a;
        --button-bg: #bd93f9;
        --button-hover: #ff79c6;
        --tooltip-bg: #1d1e26;
        --tooltip-border: #6272a4;
    }
    [data-theme="one-dark"] {
        --bg-primary: #282c34;
        --bg-secondary: #21252b;
        --bg-tertiary: #2c313a;
        --bg-hover: #2c313a;
        --text-primary: #abb2bf;
        --text-secondary: #5c6370;
        --accent-blue: #61afef;
        --accent-green: #98c379;
        --accent-orange: #d19a66;
        --border-color: #181a1f;
        --button-bg: #4d78cc;
        --button-hover: #528bff;
        --tooltip-bg: #21252b;
        --tooltip-border: #5c6370;
    }
    [data-theme="github-light"] {
        --bg-primary: #ffffff;
        --bg-secondary: #f6f8fa;
        --bg-tertiary: #f0f2f5;
        --bg-hover: #eaeef2;
        --text-primary: #1f2328;
        --text-secondary: #656d76;
        --accent-blue: #0969da;
        --accent-green: #1a7f37;
        --accent-orange: #bc4c00;
        --border-color: #d1d9e0;
        --button-bg: #0969da;
        --button-hover: #0550ae;
        --tooltip-bg: #f6f8fa;
        --tooltip-border: #d1d9e0;
    }
    [data-theme="solarized-light"] {
        --bg-primary: #fdf6e3;
        --bg-secondary: #eee8d5;
        --bg-tertiary: #e8e1cc;
        --bg-hover: #e0dac7;
        --text-primary: #073642;
        --text-secondary: #839496;
        --accent-blue: #268bd2;
        --accent-green: #859900;
        --accent-orange: #cb4b16;
        --border-color: #d3cbb7;
        --button-bg: #268bd2;
        --button-hover: #1a6da8;
        --tooltip-bg: #eee8d5;
        --tooltip-border: #839496;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Segoe UI', 'SF Pro Display', -apple-system, sans-serif;
        background: var(--bg-primary);
        color: var(--text-primary);
        line-height: 1.6;
        padding: 40px;
        max-width: 1600px;
        margin: 0 auto;
    }
    h1 { font-size: 28px; margin-bottom: 20px; color: var(--text-primary);
         border-bottom: 2px solid var(--border-color); padding-bottom: 15px; }
    .metadata {
        background: var(--bg-tertiary);
        padding: 15px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    .meta-row { display: flex; flex-wrap: wrap; gap: 25px; }
    .meta-item { display: flex; gap: 8px; align-items: center; }
    .meta-label { color: var(--text-secondary); font-size: 13px; }
    .meta-value { color: var(--text-primary); font-family: 'Consolas', monospace; font-size: 13px; }
    .meta-datasources { display: flex; flex-direction: column; gap: 4px; margin-left: 20px; }
    .meta-datasource-item { 
        display: flex; 
        gap: 12px; 
        align-items: baseline;
        color: var(--text-primary); 
        font-family: 'Consolas', monospace; 
        font-size: 12px; 
    }
    .meta-datasource-item .step-badge {
        background: var(--button-bg);
        color: #fff;
        padding: 1px 6px;
        border-radius: 3px;
        font-size: 11px;
    }
    .kernel-fields-config {
        position: relative;
        display: inline-block;
    }
    .kernel-fields-panel {
        position: absolute;
        top: 100%;
        left: 0;
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 12px;
        min-width: 200px;
        z-index: 1000;
        display: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        margin-top: 4px;
    }
    .kernel-fields-panel.visible {
        display: block;
    }
    .kernel-fields-panel label {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        cursor: pointer;
        font-size: 13px;
        color: var(--text-primary);
    }
    .kernel-fields-panel input[type="checkbox"] {
        cursor: pointer;
    }
    .kernel-fields-actions {
        display: flex;
        gap: 8px;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid var(--border-color);
    }
    .kernel-fields-actions button {
        flex: 1;
        padding: 4px 8px;
        font-size: 11px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        color: var(--text-primary);
        border-radius: 3px;
        cursor: pointer;
    }
    .kernel-fields-actions button:hover {
        background: var(--bg-hover);
    }
    .controls {
        background: var(--bg-tertiary);
        padding: 15px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 15px;
        flex-wrap: wrap;
    }
    .controls label { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 13px; }
    .controls select {
        background: var(--bg-secondary);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
        padding: 6px 12px;
        border-radius: 4px;
        font-size: 13px;
        cursor: pointer;
    }
    .controls button {
        background: var(--button-bg);
        color: #ffffff;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
        transition: background 0.2s;
    }
    .controls button:hover { background: var(--button-hover); }
    .tree { background: var(--bg-secondary); border-radius: 8px; padding: 20px; position: relative; }
    .tree-root { list-style: none; }
    .tree-children { list-style: none; padding-left: 24px; overflow: hidden; transition: max-height 0.25s ease-out; }
    .tree-node.collapsed > .tree-children { max-height: 0; }
    .tree-node.expanded > .tree-children { max-height: 50000px; }
    .node-header {
        display: flex;
        align-items: center;
        padding: 5px 10px;
        border-radius: 4px;
        cursor: pointer;
        transition: background 0.15s;
        flex-wrap: wrap;
    }
    .node-header:hover { background: var(--bg-hover); }
    .node-toggle {
        width: 16px;
        font-size: 10px;
        color: var(--text-secondary);
        text-align: center;
        flex-shrink: 0;
        transition: transform 0.2s;
    }
    .tree-node.collapsed > .node-header .node-toggle { transform: rotate(0deg); }
    .tree-node.expanded > .node-header .node-toggle { transform: rotate(90deg); }
    .tree-node.leaf > .node-header .node-toggle { visibility: hidden; }
    .tree-node.kernel-only > .node-header .node-toggle { visibility: hidden; }
    .node-name {
        flex: 1;
        margin-left: 8px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 14px;
        min-width: 150px;
    }
    .node-semantic {
        color: var(--accent-orange);
        font-size: 11px;
        font-style: italic;
        font-weight: normal;
        margin-left: 6px;
    }
    .node-semantic-wrapper {
        display: inline-flex;
        align-items: center;
        color: var(--accent-orange);
        font-size: 11px;
        font-style: italic;
        margin-left: 6px;
    }
    .node-semantic-truncated {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 400px;
    }
    .node-semantic-full {
        display: none;
    }
    .node-semantic-wrapper.expanded .node-semantic-truncated {
        display: none;
    }
    .node-semantic-wrapper.expanded .node-semantic-full {
        display: inline;
        white-space: normal;
    }
    .semantic-expand-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        margin-left: 4px;
        flex-shrink: 0;
        user-select: none;
        width: 18px;
        height: 18px;
        border: none;
        border-radius: 3px;
        background: var(--accent-orange);
        padding: 0;
        transition: background 0.15s;
    }
    .semantic-expand-btn svg {
        width: 12px;
        height: 12px;
        fill: var(--bg-primary);
        transition: transform 0.2s;
    }
    .node-semantic-wrapper.expanded .semantic-expand-btn {
        background: var(--accent-blue);
    }
    .node-semantic-wrapper.expanded .semantic-expand-btn svg {
        transform: rotate(180deg);
    }
    .semantic-expand-btn:hover {
        opacity: 0.85;
    }
    .kernel-semantic {
        color: var(--accent-orange);
        font-size: 11px;
        font-style: italic;
        margin-left: 4px;
    }
    .kernel-count, .stream-count {
        color: var(--text-secondary);
        font-size: 11px;
        margin-left: 4px;
    }
    .tree-node.hidden-kernel {
        display: none;
    }
    .kernel-meta { 
        color: var(--text-secondary); 
        font-size: 11px; 
        margin-left: 28px; 
        width: calc(100% - 28px);
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 2px 16px;
        font-family: 'Consolas', monospace;
    }
    .kernel-meta-item {
        display: flex;
        align-items: flex-start;
        gap: 4px;
        min-width: 0;
    }
    .kernel-meta-label { 
        color: var(--text-secondary); 
        flex-shrink: 0;
    }
    .kernel-meta-value {
        color: var(--text-primary);
        word-break: break-all;
        overflow-wrap: break-word;
    }
    .kernel-meta-item.shape-semantic-tip {
        position: relative;
        cursor: help;
    }
    .kernel-meta-item.shape-semantic-tip::after {
        content: attr(data-shape-semantic);
        position: absolute;
        bottom: calc(100% + 5px);
        left: 0;
        background: rgba(20,22,34,0.97);
        color: #e8c77a;
        border: 1px solid rgba(232,199,122,0.35);
        padding: 5px 9px;
        border-radius: 5px;
        font-size: 11px;
        font-family: 'Consolas', monospace;
        white-space: normal;
        max-width: 480px;
        min-width: 180px;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.15s;
        z-index: 300;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        line-height: 1.5;
    }
    .kernel-meta-item.shape-semantic-tip:hover::after {
        opacity: 1;
    }
    .node-duration {
        text-align: right;
        min-width: 200px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 12px;
        display: flex;
        justify-content: flex-end;
        gap: 6px;
    }
    .duration-us { color: var(--accent-green); }
    .duration-ms { color: var(--accent-orange); font-size: 11px; }
    .duration-pct { color: var(--accent-blue); font-weight: bold; min-width: 65px; }
    .tree-node[data-type="kernel"] .node-name {
        color: var(--accent-blue);
        font-style: italic;
        font-size: 13px;
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .tree-node[data-type="kernel"] .node-duration {
        margin-left: auto;
    }
    .kernel-info-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        background: var(--accent-blue);
        color: #fff;
        border-radius: 50%;
        cursor: pointer;
        margin-left: 4px;
        flex-shrink: 0;
        user-select: none;
        border-bottom: none;
        padding: 0;
        border: none;
    }
    .kernel-info-btn svg {
        width: 12px;
        height: 12px;
        fill: #fff;
    }
    .kernel-info-btn:hover {
        opacity: 0.8;
    }
    .node-header[title] { cursor: help; }
    .node-spacer { width: 16px; flex-shrink: 0; }
    .tree-node.leaf > .node-header { cursor: pointer; }
    
    /* Kernel Tooltip Styles */
    .kernel-tooltip {
        position: fixed;
        background: var(--tooltip-bg);
        border: 1px solid var(--tooltip-border);
        border-radius: 8px;
        padding: 12px 16px;
        max-width: 1200px;
        max-height: 80vh;
        overflow-y: auto;
        z-index: 10000;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        font-size: 12px;
        display: none;
    }
    .kernel-tooltip.visible { display: block; }
    .kernel-tooltip-header {
        font-weight: bold;
        font-size: 14px;
        margin-bottom: 8px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--tooltip-border);
        color: var(--accent-blue);
        word-break: break-all;
    }
    .kernel-tooltip-semantic {
        background: rgba(79, 193, 255, 0.1);
        border-left: 3px solid var(--accent-blue);
        padding: 6px 10px;
        margin-bottom: 10px;
        font-style: italic;
        color: var(--text-secondary);
    }
    .kernel-tooltip-container {
        width: 100%;
    }
    .kernel-tooltip-row {
        display: flex;
        gap: 16px;
        margin-bottom: 8px;
    }
    .kernel-tooltip-row:last-child {
        margin-bottom: 0;
    }
    .kernel-tooltip-group {
        flex: 1;
        min-width: 160px;
    }
    .kernel-tooltip-group-grid {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 2px 8px;
    }
    .kernel-tooltip-label {
        font-weight: 500;
        color: var(--text-secondary);
        white-space: nowrap;
        font-size: 11px;
    }
    .kernel-tooltip-value {
        color: var(--text-primary);
        word-break: break-all;
        font-size: 11px;
    }
    .kernel-tooltip-section {
        font-weight: bold;
        color: var(--accent-orange);
        padding: 6px 0 4px 0;
        font-size: 12px;
        border-bottom: 1px solid var(--tooltip-border);
        margin-bottom: 4px;
    }
    .kernel-tooltip-full {
        grid-column: 1 / -1;
        display: flex;
        gap: 8px;
    }
    .kernel-tooltip-full .kernel-tooltip-label {
        flex-shrink: 0;
        }
    
    /* Timeline Styles - Module Schematic View */
.timeline-section {
         background: var(--bg-secondary);
         border-radius: 8px;
         padding: 20px;
         margin-top: 20px;
     }
     .timeline-header {
         display: flex;
         justify-content: space-between;
         align-items: center;
         margin-bottom: 15px;
     }
     .timeline-header h2 {
         font-size: 18px;
         color: var(--text-primary);
         margin: 0;
     }
     .timeline-hint {
         font-size: 12px;
         color: var(--text-secondary);
     }
     .timeline-container {
         position: relative;
         overflow-x: auto;
         overflow-y: visible;
     }
     .timeline-overview {
         margin: 16px 0;
     }
     .timeline-overview-title {
         font-size: 14px;
         color: var(--text-primary);
         margin-bottom: 12px;
         font-weight: 500;
     }
     .timeline-overview-list {
         border: 1px solid var(--border-color);
         border-radius: 6px;
         padding: 8px;
         background: var(--bg-tertiary);
     }
     .timeline-node-item {
         display: flex;
         align-items: center;
         padding: 10px 12px;
         margin: 4px 0;
         background: var(--bg-secondary);
         border-radius: 6px;
         cursor: pointer;
         transition: background 0.15s;
     }
     .timeline-node-item:hover {
         background: var(--bg-hover);
     }
     .timeline-node-item.has-children:hover {
         background: rgba(79, 193, 255, 0.1);
     }
     .node-expand-icon {
         width: 20px;
         font-size: 12px;
         color: var(--text-secondary);
         text-align: center;
     }
     .timeline-node-item.has-children .node-expand-icon {
         color: var(--accent-blue);
     }
     .node-name {
         flex: 1;
         font-weight: 500;
         color: var(--text-primary);
     }
     .node-streams {
         font-size: 11px;
         color: var(--text-secondary);
         margin: 0 12px;
         white-space: nowrap;
     }
     .node-duration {
         font-size: 11px;
         color: var(--accent-green);
         margin-right: 12px;
         white-space: nowrap;
     }
     .node-kernels {
         font-size: 11px;
         color: var(--text-secondary);
         white-space: nowrap;
     }
     .timeline-expand-area {
         margin: 16px 0;
         padding: 16px;
         background: var(--bg-tertiary);
         border-radius: 8px;
         border: 2px solid var(--accent-blue);
     }
     .expand-header {
         display: flex;
         align-items: center;
         margin-bottom: 16px;
     }
      .expand-close {
          background: var(--bg-secondary);
          border: 1px solid var(--border-color);
          border-radius: 4px;
          padding: 4px 12px;
          color: var(--text-secondary);
          cursor: pointer;
          font-size: 12px;
          margin-right: 12px;
      }
      .expand-close:hover {
          background: var(--bg-hover);
          color: var(--text-primary);
      }
      .expand-breadcrumb {
          display: flex;
          align-items: center;
          gap: 4px;
          flex: 1;
          min-width: 0;
          overflow-x: auto;
      }
      .breadcrumb-item {
          font-size: 12px;
          color: var(--accent-blue);
          cursor: pointer;
          white-space: nowrap;
          padding: 2px 6px;
          border-radius: 3px;
          transition: background 0.15s;
      }
      .breadcrumb-item:hover {
          background: rgba(79, 193, 255, 0.1);
      }
      .breadcrumb-item.current {
          color: var(--text-primary);
          font-weight: 600;
          cursor: default;
      }
      .breadcrumb-item.current:hover {
          background: transparent;
      }
      .breadcrumb-sep {
          color: var(--text-secondary);
          font-size: 10px;
          flex-shrink: 0;
      }
     .expand-title {
         font-weight: bold;
         color: var(--accent-blue);
         font-size: 14px;
     }
     .expand-gantt {
         margin: 16px 0;
     }
     .gantt-header {
         font-size: 13px;
         color: var(--text-primary);
         margin-bottom: 8px;
     }
     .gantt-hint {
         font-size: 11px;
         color: var(--text-secondary);
     }
     .gantt-container {
         background: var(--bg-secondary);
         border-radius: 6px;
         padding: 12px;
         border: 1px solid var(--border-color);
     }
      .gantt-stream-group {
          margin: 8px 0;
      }
      .gantt-stream-row {
          display: flex;
          align-items: center;
          min-height: 32px;
      }
      .gantt-stream-label {
          width: 90px;
          font-size: 11px;
          color: var(--text-secondary);
          flex-shrink: 0;
      }
      .gantt-bars {
          flex: 1;
          position: relative;
          height: 28px;
          background: rgba(0,0,0,0.15);
          border-radius: 4px;
          overflow: visible;
      }
      .gantt-bar {
          position: absolute;
          height: 20px;
          top: 4px;
          border-radius: 3px;
          cursor: pointer;
          transition: opacity 0.15s, box-shadow 0.15s;
      }
       .gantt-bar:hover {
           opacity: 0.85;
           z-index: 10;
           box-shadow: 0 0 8px rgba(255,255,255,0.4);
       }
       .gantt-bar-secondary {
           height: 16px;
           top: 6px;
       }
      .gantt-bar-arrow {
          position: absolute;
          bottom: -5px;
          left: 50%;
          transform: translateX(-50%);
          width: 0;
          height: 0;
          border-left: 4px solid transparent;
          border-right: 4px solid transparent;
          border-top: 5px solid;
      }
      .gantt-labels-row {
          position: relative;
          min-height: 22px;
          margin-left: 90px;
          margin-top: 2px;
      }
      .gantt-label {
          position: absolute;
          font-size: 10px;
          white-space: nowrap;
          transform: translateX(-50%);
          padding: 1px 5px;
          border-radius: 3px;
          background: var(--bg-tertiary);
      }
      .gantt-label::before {
          content: '';
          position: absolute;
          top: -4px;
          left: 50%;
          transform: translateX(-50%);
          width: 0;
          height: 0;
          border-left: 3px solid transparent;
          border-right: 3px solid transparent;
          border-bottom: 4px solid var(--bg-tertiary);
      }
     .gantt-time-axis {
         display: flex;
         justify-content: space-between;
         margin-top: 8px;
         padding-top: 8px;
         border-top: 1px solid var(--border-color);
         font-size: 10px;
         color: var(--text-secondary);
     }
     .expand-tree {
         margin-top: 16px;
     }
     .expand-tree-title {
         font-size: 13px;
         color: var(--text-primary);
         margin-bottom: 8px;
     }
     .tree-hint {
         font-size: 11px;
         color: var(--text-secondary);
     }
     .expand-tree-content {
         background: var(--bg-secondary);
         border-radius: 6px;
         padding: 8px 12px;
         border: 1px solid var(--border-color);
     }
     .tree-item {
         display: flex;
         align-items: center;
         padding: 6px 8px;
         margin: 2px 0;
         border-radius: 4px;
         cursor: default;
         transition: background 0.15s;
     }
     .tree-item.clickable {
         cursor: pointer;
     }
     .tree-item.clickable:hover {
         background: rgba(79, 193, 255, 0.1);
     }
     .tree-icon {
         width: 20px;
         font-size: 12px;
         color: var(--text-secondary);
         text-align: center;
         flex-shrink: 0;
     }
     .tree-item.clickable .tree-icon {
         color: var(--accent-blue);
     }
     .tree-name {
         flex: 1;
         font-size: 12px;
         color: var(--text-primary);
     }
     .tree-streams {
         font-size: 10px;
         color: var(--text-secondary);
         margin: 0 8px;
         white-space: nowrap;
     }
     .tree-duration {
         font-size: 10px;
         color: var(--accent-green);
         white-space: nowrap;
     }
     .timeline-tooltip {
         position: fixed;
         background: var(--tooltip-bg);
         border: 1px solid var(--tooltip-border);
         border-radius: 6px;
         padding: 10px 12px;
         font-size: 12px;
         z-index: 10000;
         box-shadow: 0 4px 12px rgba(0,0,0,0.4);
         max-width: 400px;
         display: none;
     }
     .timeline-tooltip.visible {
         display: block;
     }
     .timeline-tooltip-title {
         font-weight: bold;
         color: var(--accent-blue);
         margin-bottom: 6px;
     }
     .timeline-tooltip-row {
         display: flex;
         justify-content: space-between;
         gap: 20px;
         margin-bottom: 3px;
         color: var(--text-primary);
     }
     .timeline-tooltip-label {
         color: var(--text-secondary);
     }
     .timeline-tooltip-streams {
         margin-top: 6px;
         padding-top: 6px;
         border-top: 1px solid var(--tooltip-border);
         font-size: 11px;
     }
     .timeline-detail-panel {
         margin-top: 15px;
         background: var(--bg-tertiary);
         border-radius: 6px;
         padding: 15px;
         display: none;
     }
     .timeline-detail-panel.visible {
         display: block;
     }
     .timeline-detail-header {
         display: flex;
         justify-content: space-between;
         align-items: center;
         margin-bottom: 10px;
     }
     .timeline-detail-title {
         font-weight: bold;
         color: var(--accent-blue);
     }
     .timeline-detail-close {
         background: transparent;
         border: none;
         color: var(--text-secondary);
         cursor: pointer;
         font-size: 18px;
         line-height: 1;
     }
     .timeline-detail-close:hover {
         color: var(--text-primary);
     }
      .timeline-detail-ops {
          background: var(--bg-secondary);
          border-radius: 4px;
          padding: 12px;
      }
      .timeline-stream-row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px solid var(--border-color);
          gap: 6px;
      }
      .timeline-stream-row:last-child {
          border-bottom: none;
      }
      .timeline-stream-label {
          width: 100px;
          flex-shrink: 0;
          font-size: 11px;
          font-weight: 500;
          padding: 4px 8px;
          border-radius: 3px;
          text-align: center;
      }
       .timeline-stream-ops {
           flex: 1;
           position: relative;
           height: 26px;
           background: rgba(0,0,0,0.12);
           border-radius: 4px;
       }
       .timeline-detail-bar {
           position: absolute;
           height: 22px;
           top: 2px;
           border-radius: 3px;
           font-size: 9px;
           color: #fff;
           display: flex;
           align-items: center;
           justify-content: center;
           overflow: hidden;
           cursor: pointer;
           transition: opacity 0.15s, box-shadow 0.15s;
       }
       .timeline-detail-bar:hover {
           opacity: 0.85;
           z-index: 10;
           box-shadow: 0 0 6px rgba(255,255,255,0.3);
       }
       .covered-bar {
           background-image: repeating-linear-gradient(
               45deg, transparent, transparent 3px,
               rgba(255,255,255,0.18) 3px, rgba(255,255,255,0.18) 6px
           ) !important;
           opacity: 0.55 !important;
       }
       .covered-badge {
           font-size: 10px;
           background: rgba(255,120,100,0.25);
           color: #ff7864;
           border: 1px solid rgba(255,120,100,0.45);
           border-radius: 3px;
           padding: 0 4px;
           margin-left: 5px;
           vertical-align: middle;
           white-space: nowrap;
       }
     </style>
    
    '''


JS_TEMPLATE = """
    <script>
    let currentTooltip = null;
    const tooltipData = @@TOOLTIP_JSON@@;
    const defaultFields = @@FIELDS_JSON@@;
    const tlData = @@TL_JSON@@;

    function showTooltip(el) {
        const idx = el.dataset.index;
        
        if (currentTooltip && currentTooltip.classList.contains('visible') && 
            currentTooltip.dataset.currentIdx === idx) {
            hideTooltip();
            return;
        }
        
        if (!tooltipData[idx]) return;
        
        if (!currentTooltip) {
            currentTooltip = document.createElement('div');
            currentTooltip.className = 'kernel-tooltip';
            document.body.appendChild(currentTooltip);
        }
        
        currentTooltip.innerHTML = tooltipData[idx];
        currentTooltip.classList.add('visible');
        currentTooltip.dataset.currentIdx = idx;
        currentTooltip.style.left = '';
        currentTooltip.style.top = '';
        currentTooltip.style.right = '';
        
        const rect = el.getBoundingClientRect();
        currentTooltip.style.position = 'fixed';
        
        const tooltipEl = currentTooltip;
        const tw = tooltipEl.offsetWidth;
        const th = tooltipEl.offsetHeight;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        
        let left = rect.right + 12;
        let top = rect.top;
        
        if (left + tw > vw - 10) {
            left = Math.max(10, vw - tw - 10);
        }
        if (top + th > vh - 10) {
            top = Math.max(10, vh - th - 10);
        }
        if (top < 10) top = 10;
        
        currentTooltip.style.left = left + 'px';
        currentTooltip.style.top = top + 'px';
    }
    
    function hideTooltip() {
        if (currentTooltip) {
            currentTooltip.classList.remove('visible');
        }
    }
    
    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('report-theme', theme);
        document.getElementById('theme-select').value = theme;
    }
    
    function initTheme() {
        const saved = localStorage.getItem('report-theme') || '@@DEFAULT_THEME@@';
        applyTheme(saved);
    }
    
    function toggleKernels(visible) {
        document.querySelectorAll('.tree-node[data-type="kernel"]').forEach(node => {
            if (visible) {
                node.classList.remove('hidden-kernel');
            } else {
                node.classList.add('hidden-kernel');
            }
        });
        if (visible) {
            document.querySelectorAll('.tree-node[data-type="kernel"]').forEach(kernel => {
                let parent = kernel.parentElement;
                while (parent) {
                    if (parent.classList.contains('tree-node') && parent.classList.contains('collapsed')) {
                        parent.classList.remove('collapsed');
                        parent.classList.add('expanded');
                    }
                    parent = parent.parentElement;
                }
            });
        }
    }
    
    function updateKernelMetaFields() {
        const panel = document.getElementById('kernel-fields-panel');
        const checked = Array.from(panel.querySelectorAll('input:checked')).map(cb => cb.value);
        document.querySelectorAll('.kernel-meta').forEach(meta => {
            meta.querySelectorAll('.kernel-meta-item').forEach(item => {
                const field = item.dataset.field;
                item.style.display = checked.includes(field) ? 'flex' : 'none';
            });
        });
    }

 /* ========== Timeline Logic ========== */
      let tlTooltip = null;
      let currentExpandedNode = null;
      let navHistory = [];

     function formatUs(us) {
         if (us >= 1000) return (us / 1000).toFixed(1) + 'ms';
         return us.toFixed(1) + 'us';
     }

     function initTimelineTooltip() {
         if (!tlTooltip) {
             tlTooltip = document.createElement('div');
             tlTooltip.className = 'timeline-tooltip';
             document.body.appendChild(tlTooltip);
         }
     }

      function showTimelineTooltip(el, barInfo) {
          initTimelineTooltip();
          let streamInfo = '';
          if (barInfo.streams && barInfo.streams.length > 0) {
              streamInfo = '<div class="timeline-tooltip-streams">' +
                  '<span class="timeline-tooltip-label">Streams:</span> ' +
                  barInfo.streams.map(s => 'Stream ' + s).join(', ') + '</div>';
          }
          const countSuffix = barInfo.multiplier > 1 ? ' (×' + barInfo.multiplier + ')' : '';
          const hasChildrenHint = barInfo.has_children ? '点击展开子节点' : '点击查看算子详情';
          tlTooltip.innerHTML =
              '<div class="timeline-tooltip-title">' + barInfo.name + countSuffix + '</div>' +
              '<div class="timeline-tooltip-row"><span class="timeline-tooltip-label">时间:</span> ' +
              formatUs(barInfo.duration) + '</div>' +
              '<div class="timeline-tooltip-row"><span class="timeline-tooltip-label">Kernels:</span> ' +
              barInfo.kernel_count + '</div>' +
              streamInfo +
              '<div style="margin-top:6px;color:var(--text-secondary);font-size:11px">' + hasChildrenHint + '</div>';
          tlTooltip.classList.add('visible');
          const rect = el.getBoundingClientRect();
          const vw = window.innerWidth;
          const vh = window.innerHeight;
          let left = rect.right + 10;
          let top = rect.top;
          if (left + 320 > vw) left = Math.max(10, rect.left - 330);
          if (top + 180 > vh) top = Math.max(10, vh - 190);
          if (top < 10) top = 10;
          tlTooltip.style.left = left + 'px';
          tlTooltip.style.top = top + 'px';
      }

     function hideTimelineTooltip() {
         if (tlTooltip) tlTooltip.classList.remove('visible');
     }

       function showOpsDetail(nodeIndex) {
           if (!tlData.bar_data || !tlData.bar_data[nodeIndex]) return;
           const bar = tlData.bar_data[nodeIndex];
           const panel = document.getElementById('timeline-detail-panel');
           const title = document.getElementById('timeline-detail-title');
           const opsContainer = document.getElementById('timeline-detail-ops');

           const countSuffix = bar.multiplier > 1 ? ' (×' + bar.multiplier + ')' : '';
           title.textContent = bar.name + countSuffix + ' - 算子列表';

           const allOps = [];
           if (bar.per_stream_ops) {
               for (const sid in bar.per_stream_ops) {
                   for (const op of bar.per_stream_ops[sid]) {
                       allOps.push(op);
                   }
               }
           }
           if (allOps.length === 0) {
               opsContainer.innerHTML = '<div style="padding:10px;color:var(--text-secondary)">无算子数据</div>';
               panel.classList.add('visible');
               return;
           }

           const timeMin = Math.min(...allOps.map(o => o.start));
           const timeMax = Math.max(...allOps.map(o => o.end));
           const timeDuration = Math.max(1, timeMax - timeMin);

           const streamColors = {};
           const palette = ['#4fc1ff', '#6a9955', '#ce9178', '#c586c0', '#569cd6', '#dcdcaa', '#e06c75'];
           let ci = 0;
           const sortedSids = Object.keys(bar.per_stream_ops).sort((a, b) => Number(a) - Number(b));
           for (const sid of sortedSids) {
               streamColors[sid] = palette[ci % palette.length];
               ci++;
           }

           // Determine dominant stream (most ops)
           const dominantSid = sortedSids.reduce((a, b) =>
               (bar.per_stream_ops[a].length >= bar.per_stream_ops[b].length ? a : b), sortedSids[0]);
           const dominantOps = (bar.per_stream_ops[dominantSid] || []).map(o => ({
               start: o.start, end: o.end
           }));
           function isCoveredByDominant(op) {
               return dominantOps.some(d => d.start < op.end && d.end > op.start);
           }

           let html = '';
           for (const sid of sortedSids) {
               const ops = bar.per_stream_ops[sid].sort((a, b) => a.start - b.start);
               const color = streamColors[sid];
               const isAux = sid !== dominantSid;
               const coveredCount = isAux ? ops.filter(op => isCoveredByDominant(op)).length : 0;
               const coveredBadge = (isAux && coveredCount > 0)
                   ? '<span class="covered-badge">' + coveredCount + ' covered</span>' : '';
               html += '<div class="timeline-stream-row">';
               html += '<span class="timeline-stream-label" style="background:' + color +
                   '22;color:' + color + ';border:1px solid ' + color + '44">Stream ' + sid +
                   ' (' + ops.length + ')' + coveredBadge + '</span>';
               html += '<div class="timeline-stream-ops">';
               ops.forEach((op, opIndex) => {
                   const leftPct = ((op.start - timeMin) / timeDuration) * 100;
                   const widthPct = Math.max(1, (op.duration / timeDuration) * 100);
                   const shortName = op.name.length > 10 ? op.name.substring(0, 8) + '..' : op.name;
                   const covered = isAux && isCoveredByDominant(op);
                   const coveredTip = covered ? ('\\n⚠ covered by stream ' + dominantSid) : '';
                   const tipText = op.name + '\\n历时: ' + formatUs(op.duration) +
                       '\\nStart: ' + formatUs(op.start) + coveredTip;
                   const showText = widthPct > 6;
                   // Alternating colors: even = full opacity, odd = semi-transparent + top border
                   const isEven = opIndex % 2 === 0;
                   const barAlpha = isEven ? 'ee' : '88';
                   const borderExtra = isEven ? '' : ';border-top:2px solid ' + color + 'cc';
                   const coveredClass = covered ? ' covered-bar' : '';
                   html += '<span class="timeline-detail-bar' + coveredClass + '" style="left:' +
                       leftPct.toFixed(1) + '%;width:' + widthPct.toFixed(1) + '%;background:' +
                       color + barAlpha + borderExtra + '" title="' + tipText + '">' +
                       (showText ? shortName : '') + '</span>';
               });
               html += '</div></div>';
           }
           opsContainer.innerHTML = html;
           panel.classList.add('visible');
           panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
       }

       function renderGantt(parentNode, children) {
           const container = document.getElementById('gantt-container');
           if (!container || !children || children.length === 0) {
               container.innerHTML = '<div style="padding:10px;color:var(--text-secondary)">无子节点数据</div>';
               return;
           }

           const parentStart = parentNode.start;
           const parentDuration = parentNode.duration || 1;
           const allStreams = new Set();
           children.forEach(c => c.streams.forEach(s => allStreams.add(s)));
           const sortedStreams = Array.from(allStreams).sort();

           let html = '';
           sortedStreams.forEach(stream => {
               const barsOnStream = children.filter(c => c.streams.includes(stream));
               if (barsOnStream.length === 0) return;

               html += '<div class="gantt-stream-group">';
               html += '<div class="gantt-stream-row">';
               html += '<span class="gantt-stream-label">Stream ' + stream + '</span>';
               html += '<div class="gantt-bars">';

               barsOnStream.forEach(child => {
                   const leftPct = Math.max(0, (child.start - parentStart) / parentDuration * 100);
                   const widthPct = Math.max(1.5, child.duration / parentDuration * 100);
                   const rightPct = Math.min(100, leftPct + widthPct);
                   const actualWidth = rightPct - leftPct;
                   const centerPct = leftPct + actualWidth / 2;
                   const isDominant = child.dominant_stream === stream;
                   const opacity = isDominant ? '1' : '0.4';
                   const borderStyle = isDominant ? '' : ';border:1px dashed ' + child.color;

                   html += '<div class="gantt-bar' + (isDominant ? '' : ' gantt-bar-secondary') +
                       '" style="left:' + leftPct.toFixed(1) + '%;width:' + actualWidth.toFixed(1) +
                       '%;background:' + child.color + ';opacity:' + opacity + borderStyle +
                       '" data-node-index="' + child.node_index + '" data-center="' + centerPct.toFixed(1) +
                       '" data-color="' + child.color + '">' +
                       (isDominant ? '<div class="gantt-bar-arrow" style="border-top-color:' +
                           child.color + '"></div>' : '') +
                       '</div>';
               });

               html += '</div></div>';

               html += '<div class="gantt-labels-row">';
               barsOnStream.forEach(child => {
                   const leftPct = Math.max(0, (child.start - parentStart) / parentDuration * 100);
                   const widthPct = Math.max(1.5, child.duration / parentDuration * 100);
                   const centerPct = Math.min(98, Math.max(2, leftPct + widthPct / 2));
                   const isDominant = child.dominant_stream === stream;
                   const shortName = child.name.length > 12 ? child.name.substring(0, 10) + '..' : child.name;

                   if (!isDominant) return;
                   html += '<div class="gantt-label" style="left:' + centerPct.toFixed(1) +
                       '%;color:' + child.color + ';border-color:' + child.color +
                       '66" data-center="' + centerPct.toFixed(1) + '">' +
                       shortName + '</div>';
               });
               html += '</div></div>';
           });

           const timeMarkers = [0, 0.25, 0.5, 0.75, 1].map(r => formatUs(parentStart + parentDuration * r));
           html += '<div class="gantt-time-axis">' +
               '<span>' + timeMarkers[0] + '</span>' +
               '<span>' + timeMarkers[1] + '</span>' +
               '<span>' + timeMarkers[2] + '</span>' +
               '<span>' + timeMarkers[3] + '</span>' +
               '<span>' + timeMarkers[4] + '</span></div>';

           container.innerHTML = html;

           layoutLabels(container);

           container.querySelectorAll('.gantt-bar').forEach(bar => {
               const ni = parseInt(bar.dataset.nodeIndex);
               const info = tlData.bar_data ? tlData.bar_data[ni] : null;
               if (!info) return;
               bar.addEventListener('mouseenter', () => showTimelineTooltip(bar, info));
               bar.addEventListener('mouseleave', () => setTimeout(() => {
                   if (!tlTooltip || !tlTooltip.matches(':hover')) hideTimelineTooltip(); }, 150));
               bar.addEventListener('click', (e) => { e.stopPropagation(); hideTimelineTooltip(); showOpsDetail(ni); });
           });
       }

      function layoutLabels(container) {
          container.querySelectorAll('.gantt-labels-row').forEach(row => {
              const labels = Array.from(row.querySelectorAll('.gantt-label'));
              if (labels.length === 0) return;

              labels.sort((a, b) => parseFloat(a.dataset.center) - parseFloat(b.dataset.center));

              const minGap = 10;
              for (let i = 1; i < labels.length; i++) {
                  const prev = labels[i - 1];
                  const curr = labels[i];
                  const prevLeft = parseFloat(prev.style.left);
                  let currLeft = parseFloat(curr.style.left);

                  const prevWidth = prev.offsetWidth;
                  const currWidth = curr.offsetWidth;
                  const threshold = (prevWidth + currWidth) / 2 / row.offsetWidth * 100 + minGap;

                  if (currLeft - prevLeft < threshold) {
                      currLeft = prevLeft + threshold;
                      if (currLeft > 98) currLeft = 98;
                      curr.style.left = currLeft.toFixed(1) + '%';
                  }
              }
          });
      }

      function renderTree(parentNode, children) {
          const container = document.getElementById('tree-content');
          if (!container || !children || children.length === 0) {
              container.innerHTML = '<div style="padding:10px;color:var(--text-secondary)">无子节点</div>';
              return;
          }

          const baseDepth = parentNode.depth;
          let html = '';

          function renderNode(node, depth) {
              const indent = (depth - baseDepth) * 20;
              const hasChildren = node.has_children;
              const icon = hasChildren ? '▶' : '─';
              const clickableClass = hasChildren ? 'clickable' : '';
              const streamsStr = node.streams.slice(0, 3).join(',') + (node.streams.length > 3 ? '..' : '');

              html += '<div class="tree-item ' + clickableClass + '" data-node-index="' +
                  node.node_index + '" style="padding-left:' + indent + 'px">';
              html += '<span class="tree-icon">' + icon + '</span>';
              html += '<span class="tree-name">' + node.name + '</span>';
              html += '<span class="tree-streams">[' + streamsStr + ']</span>';
              html += '<span class="tree-duration">' + formatUs(node.duration) + '</span>';
              html += '</div>';
          }

         children.forEach(child => renderNode(child, child.depth));
         container.innerHTML = html;

         container.querySelectorAll('.tree-item.clickable').forEach(item => {
             const ni = parseInt(item.dataset.nodeIndex);
             item.addEventListener('click', (e) => {
                 e.stopPropagation();
                 showNodeChildren(ni);
             });
             item.addEventListener('mouseenter', () => {
                 const info = tlData.bar_data ? tlData.bar_data[ni] : null;
                 if (info) showTimelineTooltip(item, info);
             });
             item.addEventListener('mouseleave', () => setTimeout(() => {
                 if (!tlTooltip || !tlTooltip.matches(':hover')) hideTimelineTooltip(); }, 150));
         });

         container.querySelectorAll('.tree-item:not(.clickable)').forEach(item => {
             const ni = parseInt(item.dataset.nodeIndex);
             item.addEventListener('click', (e) => {
                 e.stopPropagation();
                 showOpsDetail(ni);
             });
         });
     }

       function showNodeChildren(nodeIndex, addToHistory = true) {
           if (!tlData.bar_data || !tlData.bar_data[nodeIndex]) return;
           const node = tlData.bar_data[nodeIndex];
           const childrenIndices = node.children_indices || [];

           if (childrenIndices.length === 0) {
               showOpsDetail(nodeIndex);
               return;
           }

           if (addToHistory && currentExpandedNode !== null && currentExpandedNode !== nodeIndex) {
               navHistory.push(currentExpandedNode);
           }

           const children = childrenIndices.map(i => tlData.bar_data[i]).filter(c => c);

           const expandArea = document.getElementById('timeline-expand-area');
           const title = document.getElementById('expand-title');

            const countSuffix = node.multiplier > 1 ? ' (×' + node.multiplier + ')' : '';
            title.textContent = node.name + countSuffix + ' - 子节点多流时序';

           renderGantt(node, children);
           renderTree(node, children);
           renderBreadcrumb(nodeIndex);

           currentExpandedNode = nodeIndex;
           expandArea.style.display = 'block';
           expandArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
       }

       function renderBreadcrumb(currentNodeIndex) {
           const bcContainer = document.getElementById('expand-breadcrumb');
           if (!bcContainer) return;

           const pathIndices = [];
           let idx = currentNodeIndex;
           while (idx >= 0 && tlData.bar_data[idx]) {
               pathIndices.unshift(idx);
               idx = tlData.bar_data[idx].parent_index;
           }

           let html = '';
           pathIndices.forEach((ni, i) => {
               const info = tlData.bar_data[ni];
               const isCurrent = (ni === currentNodeIndex);
               const countSuffix = info.multiplier > 1 ? ' ×' + info.multiplier : '';
               const label = info.name + countSuffix;

               if (i > 0) {
                   html += '<span class="breadcrumb-sep">›</span>';
               }
               html += '<span class="breadcrumb-item' + (isCurrent ? ' current' : '') +
                   '" data-node-index="' + ni + '">' + label + '</span>';
           });

           bcContainer.innerHTML = html;

           bcContainer.querySelectorAll('.breadcrumb-item:not(.current)').forEach(item => {
               const ni = parseInt(item.dataset.nodeIndex);
               item.addEventListener('click', (e) => {
                   e.stopPropagation();
                   const targetIdx = navHistory.indexOf(ni);
                   if (targetIdx >= 0) {
                       navHistory = navHistory.slice(0, targetIdx);
                   }
                   showNodeChildren(ni, false);
               });
           });
       }

       function goBackToParent() {
           if (navHistory.length === 0) {
               hideExpandArea();
               return;
           }
           const prevNodeIndex = navHistory.pop();
           showNodeChildren(prevNodeIndex, false);
       }

      function hideExpandArea() {
          const expandArea = document.getElementById('timeline-expand-area');
          if (expandArea) {
              expandArea.style.display = 'none';
              currentExpandedNode = null;
              navHistory = [];
          }
      }
    
    document.addEventListener('DOMContentLoaded', function() {
        let kernelsVisible = true;
        const kernelBtn = document.getElementById('toggle-kernels-btn');
        kernelBtn.addEventListener('click', () => {
            kernelsVisible = !kernelsVisible;
            toggleKernels(kernelsVisible);
            kernelBtn.textContent = kernelsVisible ?
                '\u9690\u85cfKernel\u5e8f\u5217' : '\u663e\u793aKernel\u5e8f\u5217';
        });
        
        let kernelMetaVisible = true;
        const kernelMetaBtn = document.getElementById('toggle-kernel-meta-btn');
        kernelMetaBtn.addEventListener('click', () => {
            kernelMetaVisible = !kernelMetaVisible;
            document.querySelectorAll('.kernel-meta').forEach(el => {
                el.style.display = kernelMetaVisible ? 'grid' : 'none';
            });
            kernelMetaBtn.textContent = kernelMetaVisible ?
                '\u9690\u85cfKernel\u4fe1\u606f' : '\u663e\u793aKernel\u4fe1\u606f';
        });
        
        let allExpanded = false;
        const expandBtn = document.getElementById('toggle-expand-btn');
        const depthSelect = document.getElementById('depth-select');
        function applyDepthExpansion(maxDepth) {
            document.querySelectorAll('.tree-node').forEach(node => {
                const depth = parseInt(node.dataset.depth);
                if (!node.classList.contains('leaf') && !node.classList.contains('kernel-only')) {
                    if (depth < maxDepth) {
                        node.classList.remove('collapsed');
                        node.classList.add('expanded');
                    } else {
                        node.classList.remove('expanded');
                        node.classList.add('collapsed');
                    }
                }
            });
        }
        expandBtn.addEventListener('click', () => {
            allExpanded = !allExpanded;
            if (allExpanded) {
                applyDepthExpansion(parseInt(depthSelect.value));
                expandBtn.textContent = '\u5168\u90e8\u6536\u8d77';
            } else {
                document.querySelectorAll('.tree-node:not(.leaf)').forEach(node => {
                    node.classList.remove('expanded');
                    node.classList.add('collapsed');
                });
                expandBtn.textContent = '\u5168\u90e8\u5c55\u5f00';
            }
        });

        depthSelect.addEventListener('change', () => {
            applyDepthExpansion(parseInt(depthSelect.value));
            if (allExpanded) {
                expandBtn.textContent = '\u5168\u90e8\u6536\u8d77';
            }
        });
        
        let auxiliaryVisible = false;
        const auxiliaryBtn = document.getElementById('toggle-auxiliary-btn');
        document.querySelectorAll('.tree-node[data-category="auxiliary"]').forEach(node => {
            node.style.display = 'none';
        });
        document.querySelectorAll('.timeline-node-item[data-category="auxiliary"]').forEach(node => {
            node.style.display = 'none';
        });
        auxiliaryBtn.addEventListener('click', () => {
            auxiliaryVisible = !auxiliaryVisible;
            document.querySelectorAll('.tree-node[data-category="auxiliary"]').forEach(node => {
                node.style.display = auxiliaryVisible ? '' : 'none';
            });
            document.querySelectorAll('.timeline-node-item[data-category="auxiliary"]').forEach(node => {
                node.style.display = auxiliaryVisible ? '' : 'none';
            });
            auxiliaryBtn.textContent = auxiliaryVisible ?
                '\u9690\u85cf\u8f85\u52a9\u5c42\u6b21' : '\u663e\u793a\u8f85\u52a9\u5c42\u6b21';
        });
        
        const fieldsPanel = document.getElementById('kernel-fields-panel');
        const fieldsBtn = document.getElementById('kernel-fields-btn');
        
        fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = defaultFields.includes(cb.value);
        });
        
        fieldsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fieldsPanel.classList.toggle('visible');
        });
        
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.kernel-fields-config')) {
                fieldsPanel.classList.remove('visible');
            }
        });
        
        fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', updateKernelMetaFields);
        });
        
        document.getElementById('fields-select-all').addEventListener('click', (e) => {
            e.stopPropagation();
            fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
            updateKernelMetaFields();
        });
        
        document.getElementById('fields-select-none').addEventListener('click', (e) => {
            e.stopPropagation();
            fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            updateKernelMetaFields();
        });
        
        document.getElementById('fields-reset').addEventListener('click', (e) => {
            e.stopPropagation();
            fieldsPanel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.checked = defaultFields.includes(cb.value);
            });
            updateKernelMetaFields();
        });
        
        let semanticAllExpanded = false;
        const semanticBtn = document.getElementById('toggle-semantic-btn');
        
        semanticBtn.addEventListener('click', () => {
            semanticAllExpanded = !semanticAllExpanded;
            document.querySelectorAll('.node-semantic-wrapper').forEach(w => {
                if (semanticAllExpanded) {
                    w.classList.add('expanded');
                } else {
                    const full = w.dataset.full || '';
                    if (full.length > 120) {
                        w.classList.remove('expanded');
                    }
                }
            });
            semanticBtn.textContent = semanticAllExpanded ?
                '\u6536\u8d77\u5168\u90e8\u8bed\u4e49' : '\u5c55\u5f00\u5168\u90e8\u8bed\u4e49';
        });
        
        document.getElementById('theme-select').addEventListener('change', function() {
            applyTheme(this.value);
        });
        
        document.addEventListener('click', function(e) {
            const btn = e.target.closest('.semantic-expand-btn');
            if (!btn) return;
            e.stopPropagation();
            const wrapper = btn.closest('.node-semantic-wrapper');
            if (wrapper) {
                wrapper.classList.toggle('expanded');
            }
        });
        
        document.querySelectorAll('.tree-node:not(.leaf)').forEach(node => {
            const header = node.querySelector('.node-header');
            header.addEventListener('click', (e) => {
                if (e.target.closest('[data-type="kernel"]')) return;
                if (e.target.closest('.semantic-expand-btn')) return;
                if (e.target.closest('.node-semantic-wrapper')) return;
                if (e.target.closest('.kernel-info-btn')) return;
                node.classList.toggle('collapsed');
                node.classList.toggle('expanded');
            });
        });
        
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.tree-node[data-type="kernel"]') && 
                !e.target.closest('.kernel-tooltip') &&
                !e.target.closest('.kernel-info-btn')) {
                hideTooltip();
            }
        });
        
        document.querySelectorAll('.kernel-info-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                showTooltip(btn);
            });
        });
        
        if (currentTooltip) {
            currentTooltip.addEventListener('mouseleave', hideTooltip);
        }
        
        initTheme();

/* ========== Timeline Event Listeners ========== */
         document.querySelectorAll('.timeline-node-item').forEach(item => {
             const ni = parseInt(item.dataset.nodeIndex);
             const info = tlData.bar_data ? tlData.bar_data[ni] : null;
             if (!info) return;

             item.addEventListener('mouseenter', () => showTimelineTooltip(item, info));
             item.addEventListener('mouseleave', () => setTimeout(() => {
                 if (!tlTooltip || !tlTooltip.matches(':hover')) hideTimelineTooltip(); }, 150));
             item.addEventListener('click', (e) => {
                 e.stopPropagation();
                 hideTimelineTooltip();
                 if (info.has_children) {
                     showNodeChildren(ni);
                 } else {
                     showOpsDetail(ni);
                 }
             });
         });

         if (tlTooltip) {
             tlTooltip.addEventListener('mouseleave', hideTimelineTooltip);
         }

          const expandCloseBtn = document.getElementById('expand-close-btn');
          if (expandCloseBtn) {
              expandCloseBtn.addEventListener('click', hideExpandArea);
          }

          const detailCloseBtn = document.getElementById('timeline-detail-close');
         if (detailCloseBtn) {
             detailCloseBtn.addEventListener('click', () => {
                 document.getElementById('timeline-detail-panel').classList.remove('visible');
             });
         }

         document.addEventListener('click', (e) => {
             if (!e.target.closest('.timeline-node-item') && !e.target.closest('.timeline-tooltip') &&
                 !e.target.closest('.timeline-expand-area') && !e.target.closest('.timeline-detail-panel')) {
                 hideTimelineTooltip();
             }
         });
    });
    </script>
    """
