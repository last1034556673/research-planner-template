# Research Planner Template

[English](./README.md) | 简体中文

这是一个面向科研日常工作的本地优先实验规划模板仓库，尤其适合湿实验为主、同时夹杂分析、汇报和条件任务重排的工作流。

核心特点：

- 核心规划器跨平台
- 默认只依赖本地文件
- macOS 日历同步是可选集成

## 最快上手

如果你想让别人直接用这套模板，最简单的说法就是：

1. 在 GitHub 上点 `Use this template`
2. 用这个模板创建你自己的仓库
3. clone 到本地
4. 执行下面几条命令

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
research-planner init --mode blank
research-planner prepare-report
research-planner refresh
```

如果只是想先看匿名 demo：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
research-planner --workspace ./workspace_demo init --mode demo
research-planner --workspace ./workspace_demo refresh
```

`v1.1.0` 里，`--workspace` 写在子命令前后都可以。

## 配合 AI 使用

把仓库用 Codex、Claude 或其他本地大模型打开后，可以直接说：

> 先读 `README.md` 和 `docs/ARCHITECTURE.md`，再通过 `research-planner` 帮我维护这套实验规划。

## 能力范围

- 短窗口主看板：前 7 天 + 今天 + 后 7 天
- 固定格式日报解析
- 状态日志与滚动更新
- 历史归档
- 月 / 季 / 年总结 HTML
- 匿名湿实验 demo
- 空白 starter workspace

## 三种使用层级

1. 只用核心规划器
   - 本地事件文件 + 日报 + 看板
2. 核心规划器 + 历史总结
   - 增加月度、季度、年度总结
3. 核心规划器 + macOS 可选集成
   - 增加 EventKit 日历导出与清理

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
research-planner init --mode blank
research-planner prepare-report
research-planner refresh
```

常用命令：

```bash
research-planner ingest-report --input workspace/daily_reports/YYYY-MM-DD.md
research-planner replan --input workspace/daily_reports/YYYY-MM-DD.md
research-planner doctor --json
```

默认本地工作区是 `./workspace`，已经被 `.gitignore` 忽略，不会进入公开仓库。

如果你要在本地跑开发测试：

```bash
pip install -e '.[dev]'
python -m pytest
```

## Demo

匿名 demo 在：

- [`examples/wetlab_demo/workspace_seed/`](examples/wetlab_demo/workspace_seed/)

示例输出在：

- [`dashboard.html`](examples/wetlab_demo/sample_outputs/dashboard.html)
- [`history-month.html`](examples/wetlab_demo/sample_outputs/history-month.html)
- [`history-quarter.html`](examples/wetlab_demo/sample_outputs/history-quarter.html)
- [`history-year.html`](examples/wetlab_demo/sample_outputs/history-year.html)

## 文档

- [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- [`docs/MACOS_OPTIONAL.md`](docs/MACOS_OPTIONAL.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/PRIVACY_BOUNDARY.md`](docs/PRIVACY_BOUNDARY.md)

## Agent 说明

- Codex: [`AGENTS.md`](AGENTS.md)
- Claude: [`CLAUDE.md`](CLAUDE.md)
- 通用大模型: [`docs/GENERIC_AGENT.md`](docs/GENERIC_AGENT.md)
- 生成本地 Codex skill: [`docs/MAKE_LOCAL_CODEX_SKILL.md`](docs/MAKE_LOCAL_CODEX_SKILL.md)
- 生成本地 Claude Code 配置: [`docs/MAKE_LOCAL_CLAUDE_CODE_SETUP.md`](docs/MAKE_LOCAL_CLAUDE_CODE_SETUP.md)

## 工作流规则

- [`docs/PLANNER_WORKFLOW.md`](docs/PLANNER_WORKFLOW.md)
