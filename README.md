# 内容运营 Agent（Content Operations Agent）

面试实战题二实现：**抓取真实信息源 → AI 提炼选题 → 逐条人工审核 → 生成多平台内容 → 发布前确认 → 飞书推送 + 生成 Word 文档**。

覆盖题目要求：
- 使用真实信息来源（抓取 RSS / GitHub 等真实资讯，非纯 AI 编造）
- 收集 + 生成（4 个任务中选 2 个）
- 对外发布前人工确认（发布前确认节点）

加分项：
- 自动找热点选题
- 生成平台化版本（小红书 / 公众号风格）
- 生成发布计划 / 报告
- 逐条人工审核（对选题按条号编辑 / 拒绝，按 `p` 完成才进入生成）

## 项目结构

```
ai-content-agent/
├── common/                  # 公共模块
│   ├── llm.py               # LLM 封装（OpenAI 兼容接口）
│   ├── feishu.py            # 飞书 webhook 推送
│   └── human_review.py      # 整段报告人工审核节点
├── problem2_content/        # 题二：内容运营 Agent
│   ├── main.py              # 主流程
│   ├── review_topics.py     # 选题逐条人工审核
│   ├── publish_confirm.py   # 发布前人工确认
│   └── sources.py           # 真实信息源抓取（RSS / GitHub）
├── output/                  # 输出目录（Word 文档）
├── requirements.txt
└── .env.example             # 配置模板
```

## 快速开始

### 1. 安装依赖

```bash
cd ai-content-agent
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 LLM API Key 和飞书 Webhook
```

### 3. 运行

```bash
python problem2_content/main.py
```

运行后：
1. 自动抓取真实信息源（RSS / GitHub 科技 AI 资讯）
2. 输入内容主题，AI 基于真实资讯提炼选题
3. 逐条选题审核，按 `p` 完成审核进入生成
4. 生成多平台内容（公众号 / 小红书）+ 发布计划
5. 发布前人工确认（`p` 确认发布 / `r` 拒绝）
6. 确认后推送到飞书并生成 Word 文档

## 配置说明

### LLM（OpenAI 兼容接口）

| 变量 | 说明 |
|:---|:---|
| `LLM_API_KEY` | 你的 API Key |
| `LLM_BASE_URL` | 服务商接口地址（OpenAI / DeepSeek / 通义千问 / Moonshot） |
| `LLM_MODEL` | 模型名 |

### 飞书机器人

1. 在飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人
2. 复制 Webhook 地址填入 `FEISHU_WEBHOOK`
3. 若开启签名校验，把密钥填入 `FEISHU_SECRET`

## 工作流说明

```
抓取真实信息源(RSS/GitHub) → AI基于真实资讯提炼选题
    → 逐条选题审核(e编辑/r拒绝/p完成进入生成)
    → AI生成多平台内容(公众号/小红书) → 生成发布计划
    → 发布前人工确认(p确认发布/r拒绝) → 飞书推送 + 生成Word文档
```

## 风险控制

- 使用真实信息源，每个选题标注来源(source)与链接(url)，可追溯
- 生成前有逐条选题审核节点（按条号编辑 / 拒绝，`e`/`r` 不推送，`p` 统一进入生成）
- 对外发布前有独立的人工确认节点（`r` 拒绝则不推送飞书）
- 单源抓取失败不影响其余源；LLM 失败有真实数据兜底；飞书失败不影响 Word 输出
