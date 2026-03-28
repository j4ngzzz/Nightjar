<div align="center">
  <pre>
    ╔╗╔╦╔═╗╦ ╦╔╦╗ ╦╔═╗╦═╗
    ║║║║║ ╦╠═╣ ║  ║╠═╣╠╦╝
    ╝╚╝╩╚═╝╩ ╩ ╩╚╝╩╩ ╩╩╚═
  </pre>
  <p><strong>夜鹰 — 你的 LLM 写代码，夜鹰证明它是对的。</strong></p>

  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue" alt="License" /></a>
  <a href="#快速开始"><img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python" /></a>
  <a href="https://pypi.org/project/nightjarzzz/"><img src="https://img.shields.io/pypi/v/nightjarzzz" alt="PyPI" /></a>
</div>

<br>

[English](README.md) | [中文](README-zh.md)

---

```
$ nightjar verify --spec .card/payment.card.md

  Stage 0 (preflight)    PASS    12ms
  Stage 1 (deps)         PASS    45ms
  Stage 2 (schema)       PASS    23ms
  Stage 3 (pbt)          FAIL    340ms
    INV-01 violated: counterexample x=0 -> ZeroDivisionError
  Stage 4 (formal)       SKIP

  Result: 1 violation found
  Trust: PROPERTY_VERIFIED (0.60)
```

---

## 问题

84% 的开发者在使用 AI 编程工具，但 96% 的人不完全信任生成的代码。45% 的 AI 生成代码包含 OWASP 安全漏洞。代码越写越多，验证却越来越少。

夜鹰把这个差距补上。用数学证明，不是测试。

---

## 它发现了真实的 bug

我们用夜鹰扫描了常用的 Python 库，找到了这些问题。

**fastmcp 2.14.5 — JWT 永不过期**（`server/auth/jwt_issuer.py:214`）：

```python
exp = payload.get("exp")
if exp and exp < time.time():   # "if exp" 是真值检查，不是 None 检查
    raise JoseError("Token has expired")
```

没有 `exp` 字段的 token，`exp = None`，`if None` 为 `False`，过期检查被跳过，token 永远有效。夜鹰用一个 3 行的 spec 发现了这个问题：

```
Stage 3 (pbt) FAIL — counterexample: exp=None -> token accepted
```

**httpx 0.28.1 — 空字符串导致 IndexError**（`httpx._utils.unquote`）：

```python
def unquote(value: str) -> str:
    return value[1:-1] if value[0] == value[-1] == '"' else value
    # value == "" 时抛出 IndexError
```

服务器返回 `Digest realm=,nonce=abc` 时，`realm` 值为空字符串，`unquote("")` 抛出 `IndexError`。夜鹰的 Hypothesis 阶段在 500 个样本中找到了这个反例。

---

## 安装

```bash
pip install nightjarzzz
nightjar init mymodule
nightjar verify --spec .card/mymodule.card.md
```

需要 Python 3.11+。[Dafny 4.x](https://github.com/dafny-lang/dafny/releases) 是可选的——没有 Dafny，夜鹰会用 CrossHair 和 Hypothesis，仍然能给出置信分数。

---

## 工作原理

你用 `.card.md` 文件描述代码的意图和约束。LLM 生成代码。夜鹰运行五个验证阶段——从最便宜的开始，遇到失败立即短路——最终给出证明证书或具体的反例。

五个阶段：

| 阶段 | 内容 | 耗时 |
|------|------|------|
| 0. 预检 | 语法、导入 | <100ms |
| 1. 依赖 | CVE 扫描 | <500ms |
| 2. 模式 | 类型检查（Pydantic v2） | <200ms |
| 3. 属性 | Hypothesis PBT | 300ms–8s |
| 4. 形式化 | Dafny / CrossHair 证明 | 1–30s |

简单函数跳过 Dafny，直接用 CrossHair（快约 70%）。夜鹰根据圈复杂度和 AST 深度自动判断。

Dafny 失败时，CEGIS 重试循环会解析具体的反例，再把它传给 LLM："你的 spec 在输入 X=5, Y=-3 时失败，因为……" 比原始错误信息有用得多。

---

## 快速开始

```bash
# 生成 spec 骨架
nightjar init payment

# 编辑 .card/payment.card.md，添加你的不变式

# 从 spec 生成代码
nightjar generate --model claude-sonnet-4-6

# 运行验证流水线
nightjar verify --spec .card/payment.card.md

# 快速检查（跳过 Dafny）
nightjar verify --spec .card/payment.card.md --fast
```

用环境变量切换模型：

```bash
NIGHTJAR_MODEL=claude-sonnet-4-6       # 默认
NIGHTJAR_MODEL=deepseek/deepseek-chat  # 经济选项
NIGHTJAR_MODEL=openai/o3               # 精度优先
```

---

## .card.md 格式

```yaml
---
card-version: "1.0"
id: payment
title: Payment Processor
contract:
  inputs:
    - name: balance
      type: float
      constraints: ">= 0"
  outputs:
    - name: new_balance
      type: float
      constraints: ">= 0"
invariants:
  - tier: formal
    rule: "deduct(balance, amount) requires amount <= balance ensures result >= 0"
  - tier: property
    rule: "for any balance >= 0: deposit(balance, amount) > balance"
---

## Intent
处理信用卡支付的模块，余额不能为负。
```

三种不变式层级：`example` 生成单元测试，`property` 生成 Hypothesis PBT，`formal` 生成 Dafny 证明或 CrossHair 符号检查。

---

## 免疫系统

夜鹰从生产故障中学习，规格会随着时间演进。

```
Sentry 错误 + 运行时追踪
        |
        v
   Collector (sys.monitoring，<5% 开销)
        |
        v
   挖掘器（19 种 Daikon 模板）
        |
        v
   质量过滤（Wonda 评分，过滤无意义不变式）
        |
        v
   对抗辩论（怀疑者代理尝试反驳每个候选）
        |
        v
   CrossHair + Hypothesis（用 1000+ 个输入验证）
        |
        v
   自动追加到 .card.md（规格持续演进）
```

---

## MCP 服务器

夜鹰也是 MCP 服务器，支持 Cursor、Windsurf、Claude Code、VS Code。

三个工具：`verify_contract`、`get_violations`、`suggest_fix`。

---

## 命令行参考

```
nightjar init [module]    生成 .card.md 骨架
nightjar auto "intent"    从自然语言生成 spec
nightjar generate         从 spec 生成代码
nightjar verify           运行验证流水线
nightjar verify --fast    仅运行阶段 0–3（跳过 Dafny）
nightjar build            生成 + 验证 + 编译
nightjar watch            后台守护进程，保存时自动验证
nightjar retry            反例引导的修复循环
nightjar explain          根因诊断
nightjar lock             锁定依赖到 deps.lock
nightjar badge            从上次验证生成 Shields.io 徽章
nightjar immune           运行免疫系统挖掘周期
```

---

## 延伸阅读

- [架构](docs/ARCHITECTURE.md) — 完整流水线设计
- [参考文献](docs/REFERENCES.md) — 算法背后的论文
- [贡献指南](CONTRIBUTING.md)
- [更新日志](CHANGELOG.md)
- [安全策略](SECURITY.md)

---

## 许可证

[AGPL-3.0](LICENSE)。开源免费。

商业许可证（团队无法遵从 AGPL 时）：$2,400/年（团队）· $12,000/年（企业）。联系：nightjar-license@proton.me
