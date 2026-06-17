# skill-creator-plus

> ⚠️ **本 skill 正在迭代中,不稳定。** 工作流、文件路径、脚本名、命令行参数都可能在 commit 之间无预警变更。如果你依赖它,请固定到某个 commit,不要跟分支。已知摩擦点见 [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md)。

> 📖 **English**: [README.md](README.md)

[Claude Code](https://docs.claude.com/en/docs/claude-code) 的元 skill —— 用来创建、改进、测评 Claude Code skill。它本身也是一个 skill,用来引导、lint、测试、迭代其他 skill。

## 它能做什么

三种工作流:

- **创建(Create)** —— 访谈用户,起草 SKILL.md,跑测试用例,迭代
- **改进(Improve)** —— 拿已有 skill,在当前版本上跑测试-改进循环
- **Description 优化** —— 调整 frontmatter 的 `description` 字段以提升触发准确率(独立的 eval 集,盲测对比)

测试循环会 spawn 子代理跑 `with_skill` vs `without_skill`(默认各 3 次),汇总 pass-rate / 时间 / token 成本到 benchmark,然后带你逐个看输出、收集反馈。

## 五条标准(Joe's Standards)

skill-creator-plus 产出的每个 skill 都要满足:

1. **减法过滤器(Subtraction filter)** —— 只写模型推理不出来的内容
2. **分层结构(Layered structure)** —— 通过 `SKILL.md` + `references/` 实现渐进式披露
3. **确定性用代码(Determinism in code)** —— 只有一个正确答案的任务交给脚本
4. **测试强制(Tests mandatory)** —— workspace 必须至少跑过一次测试循环
5. **代理友好的 CLI(Agent-friendly CLI)** —— 脚本要支持 `--format`、结构化错误、机器可读输出

由 `scripts/check-skill.py` 强制执行。每次 commit 前跑一遍:

```bash
python3 scripts/check-skill.py .
```

完整说明:[`references/joe-standard.md`](references/joe-standard.md)(英文)。

## 安装

```bash
git clone <repo-url> ~/.claude/skills/skill-creator-plus
```

Claude Code 会自动发现 `~/.claude/skills/` 下的 skill。当用户想创建、修改、测评、改进某个 skill 时,本 skill 会被触发。

如果你要边用边改(编辑后全局立即生效),用软链接:

```bash
git clone <repo-url> ~/src/skill-creator-plus
ln -s ~/src/skill-creator-plus ~/.claude/skills/skill-creator-plus
```

## 使用

安装后,直接用自然语言跟 agent 描述需求即可:

- "做一个把 PDF 表格转 CSV 的 skill"
- "改进我现有的 PDF skill"
- "测评一下别人发我的这个 skill"

完整工作流见 [`SKILL.md`](SKILL.md)。

## 目录结构

```
skill-creator-plus/
├── SKILL.md              # 主工作流
├── KNOWN_ISSUES.md       # 实时待办清单
├── scripts/              # scaffold, check-skill, init-workspace, aggregate ...
├── references/           # Joe's standards, schemas, 反模式剖析
├── assets/agents/        # grader / comparator / analyzer 提示词
└── tests/                # 纪律测试,输出检查,check-skill 的 pytest
```

## 贡献

本 skill 自己吃自己的狗粮 —— 用的时候撞到摩擦,**别默默绕过**。往 [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) 追加一条:你做了什么、预期是什么、实际发生了什么、(可选)一行修复建议。下一次迭代就把这个文件当待办清单。

## 协议

Apache 2.0。见 [`LICENSE.txt`](LICENSE.txt) 和 [`NOTICE`](NOTICE)。

Copyright 2026 Zhou, Man (Joe).
