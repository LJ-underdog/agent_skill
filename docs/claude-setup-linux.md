# 在新 Linux 机器上配置 Claude Code（与当前机器一致）

本文档基于当前机器（`<your-host>`）的实际可用配置，并参考 AMD 官方指南：
<https://amd.atlassian.net/wiki/spaces/SLA/pages/1243841365>

目标：在另一台 Linux 机器上用 AMD LLM Gateway 跑 Claude Code，模型、API key、环境变量都和当前机器一模一样。

---

## 一、关键配置信息（直接复制使用）

| 项目 | 值 |
| --- | --- |
| Claude Code 版本 | `2.1.76`（当前机器在用，与 AMD 网关兼容） |
| API Base URL | `https://llm-api.amd.com/Anthropic` |
| API Key（占位） | `dummy` |
| AMD LLM Gateway Key | `<YOUR_AMD_GATEWAY_KEY>` |
| 默认模型（Opus/Sonnet/Haiku 全部） | `claude-opus-4-7` |

> ⚠️ AMD 网关目前只放出 `claude-opus-4-7`，`sonnet-4.6` / `haiku-4.5` 在网关上会 403。把三个 `*_MODEL` 都设成 `claude-opus-4-7` 是当前机器实际能跑的写法。

---

## 二、安装步骤

### 1. 安装 Claude Code

官方 installer（推荐，会装到 `~/.local/share/claude/versions/<ver>/`，并在 `~/.local/bin/claude` 创建软链）：

```bash
curl -fsSL https://claude.ai/install.sh | bash -s 2.1.76
```

安装后 `claude` 是一个 ELF 可执行文件，**不依赖 Node.js**。

### 2. 把 `claude` 加进 PATH

如果 `claude --version` 已经能跑就跳过。否则在 `~/.bashrc` 加一行：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

> RHEL/CentOS 登录 shell 只读 `~/.bash_profile`，确保它会 source `~/.bashrc`：
> ```bash
> [ -f ~/.bashrc ] && source ~/.bashrc
> ```

### 3. 配置 API key 与模型（环境变量方式，与当前机器一致）

把下面这段追加到 `~/.bashrc`（推荐，跟当前机器一模一样）：

```bash
# === Claude Code / AMD LLM Gateway ===
export AMD_LLM_GATEWAY_KEY="<YOUR_AMD_GATEWAY_KEY>"
export ANTHROPIC_API_KEY="dummy"
export ANTHROPIC_BASE_URL="https://llm-api.amd.com/Anthropic"
export ANTHROPIC_CUSTOM_HEADERS="Ocp-Apim-Subscription-Key: ${AMD_LLM_GATEWAY_KEY}"
export ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-opus-4-7
export ANTHROPIC_DEFAULT_SONNET_MODEL=claude-opus-4-7
export ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-7
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export CLAUDE_CODE_SUBAGENT_MODEL="${ANTHROPIC_DEFAULT_OPUS_MODEL}"
export CLAUDE_CODE_TMPDIR="/tmp/claude-${USER}"
```

然后：

```bash
source ~/.bashrc
```

### 4. 跳过首次启动的「Select login method / Trust API key」提示

创建 `~/.claude.json`（**家目录根下，不是 `~/.claude/.claude.json`**）：

```bash
mkdir -p ~/.claude && chmod 700 ~/.claude
python3 - <<'PY'
import json, os
p = os.path.expanduser("~/.claude.json")
cfg = {}
if os.path.exists(p):
    cfg = json.load(open(p))
cfg.setdefault("customApiKeyResponses", {"approved": ["dummy"], "rejected": []})
cfg["hasCompletedOnboarding"] = True
json.dump(cfg, open(p, "w"), indent=2)
PY
```

### 5. （可选）创建 `~/.claude/settings.json`

当前机器上这文件只放了 `apiKeyHelper` 等极简内容。新机器**最简可以不建**——前面 `~/.bashrc` 的环境变量已经够用。如果要建：

```bash
cat > ~/.claude/settings.json <<'EOF'
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "apiKeyHelper": "echo {apiKey}"
}
EOF
chmod 600 ~/.claude/settings.json
```

---

## 三、验证

### 1. 验证 AMD 网关本身可达（与 Claude 无关，纯 curl）

```bash
curl -sS -X POST https://llm-api.amd.com/Anthropic/v1/messages \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -H "Ocp-Apim-Subscription-Key: $AMD_LLM_GATEWAY_KEY" \
  -d '{"model":"claude-opus-4-7","max_tokens":20,"messages":[{"role":"user","content":"ping, reply with one word"}]}'
```

期望：返回类似
```json
{"model":"claude-opus-4-7", ... "content":[{"type":"text","text":"pong"}], ...}
```

如果返回 `401` → key 错；返回 `403 Access to model ... not available` → 模型名错；返回 SSL/证书错 → 看下文 TLS 排查。

### 2. 验证 Claude Code 跑得通

```bash
claude --version          # 应输出 2.1.76 (Claude Code)
claude -p 'say hi in one word'   # 应输出一个词，例如 "Hi"
```

如果 `claude -p` 能正常返回，说明 PATH、环境变量、网关 key、模型名全对。

---

## 四、常见问题

### Q1：`403 Access to model [X] is not available`
模型名和网关不匹配。**当前 AMD 网关只有 `claude-opus-4-7` 能用**，三个 `*_MODEL` 都填它。

### Q2：TLS / 证书错（`self-signed certificate`、`unable to verify the first certificate`）
Claude Code 用的 Node.js 不读系统信任库，需要装 AMD 根证书并指给它：

```bash
# RHEL / CentOS / Fedora
sudo cp AMD_CA.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust
# 然后在 ~/.bashrc 加：
export NODE_EXTRA_CA_CERTS=/etc/pki/tls/certs/ca-bundle.crt

# Debian / Ubuntu
sudo cp AMD_CA.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
# 然后在 ~/.bashrc 加：
export NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
```

证书下载：`http://pki.amd.com/CertEnroll/` 或 Confluence 的 `AMD_CA.crt` 附件。

### Q3：长任务超时
`~/.bashrc` 里加：
```bash
export API_TIMEOUT_MS=1200000
export CLAUDE_CODE_MAX_RETRIES=20
```

### Q4：在 Docker 容器里也想用
参考当前机器 `~/.claude/projects/-home-junlin12/memory/MEMORY.md` 里 `Skill: docker-install-claude` 一节，要点：
- 把宿主机 `~/.local/share/claude/versions/2.1.76` 整个 cp 进容器
- 写 `/root/.claude-env` 包含上面那一坨 `export`
- `docker run` 时加 `-e BASH_ENV=/root/.claude-env`（`bash -c` 不读 `.bashrc`，必须用 `BASH_ENV`）

---

## 五、与当前机器对照（自检清单）

在新机器上跑这个脚本，输出应与当前机器一致：

```bash
echo "claude:           $(which claude)"
echo "version:          $(claude --version)"
echo "BASE_URL:         $ANTHROPIC_BASE_URL"
echo "API_KEY:          $ANTHROPIC_API_KEY"
echo "GATEWAY_KEY len:  ${#AMD_LLM_GATEWAY_KEY}  (应为 32)"
echo "OPUS_MODEL:       $ANTHROPIC_DEFAULT_OPUS_MODEL"
echo "SONNET_MODEL:     $ANTHROPIC_DEFAULT_SONNET_MODEL"
echo "HAIKU_MODEL:      $ANTHROPIC_DEFAULT_HAIKU_MODEL"
echo "SUBAGENT_MODEL:   $CLAUDE_CODE_SUBAGENT_MODEL"
```

当前机器输出（参考）：

```
claude:           /home/<user>/.local/bin/claude
version:          2.1.76 (Claude Code)
BASE_URL:         https://llm-api.amd.com/Anthropic
API_KEY:          dummy
GATEWAY_KEY len:  32  (应为 32)
OPUS_MODEL:       claude-opus-4-7
SONNET_MODEL:     claude-opus-4-7
HAIKU_MODEL:      claude-opus-4-7
SUBAGENT_MODEL:   claude-opus-4-7
```
