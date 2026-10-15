# 电商 RAG 知识库

模块化电商售后 RAG 问答服务。本地数据集直接入库 Milvus，MySQL 存储文档元信息，Qwen 兼容 OpenAI API 生成回答。

## 技术栈

MinerU、Milvus、BGE-M3、bge-reranker-v2-m3、Qwen（OpenAI 兼容）、MySQL（pymysql）、FastAPI + uvicorn

## 目录结构

```
RAG/
├── app/
│   ├── config.py               # 配置读取
│   ├── schemas.py              # 接口数据模型
│   ├── clients/
│   │   ├── mysql.py            # 建表 + 文档元信息 CRUD
│   │   └── milvus.py           # 集合创建 + 向量读写检索
│   ├── encoder/
│   │   ├── embedding.py        # BGE-M3 向量化
│   │   ├── reranker.py         # bge-reranker-v2-m3 二次重排
│   │   └── classifier.py       # new_bert 问题分类
│   ├── ingest/
│   │   ├── loader.py           # MinerU / 本地文档读取
│   │   ├── splitter.py         # 父子分块
│   │   └── pipeline.py         # /init_data 入库流程
│   ├── retrieve/
│   │   ├── strategies.py       # 直接 / 假设问题 / 子问题 / 回溯
│   │   └── searcher.py         # 召回 + 阈值 + 去重 + 重排
│   ├── llm/qwen.py             # 大模型调用
│   ├── rag.py                  # 问答编排
│   └── api.py                  # FastAPI 接口
├── knowledge_data/             # 本地数据集
├── models/                     # 本地模型权重
├── static/
│   ├── index.html              # 问答前端页面
│   ├── app.css
│   ├── app.js
│   └── swagger-ui/             # 本地托管, 避免 CDN 不可达导致 /docs 白屏
├── logger.py                   # 日志工具
├── config.ini.example          # 配置模板（复制为 config.ini 后填凭据）
├── train_bert.py               # 问答分类模型微调脚本
├── main.py                     # uvicorn 启动
└── requirements.txt
```

## 环境准备

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

### 配置

```powershell
copy config.ini.example config.ini
```

`config.ini` 含 API Key 与数据库密码，已被 `.gitignore` 忽略。需填写：`[mysql] password`、`[llm] dashscope_api_key`，其余保持默认即可。

### 训练问题分类模型

```powershell
python train_bert.py
```

用 `bert_data/bert_train.jsonl` 微调 `models/bert-base-chinese`，产出 `models/new_bert`（206 条样本，5 epoch，验证集准确率 1.0）。

### MinerU（用于 PDF/DOCX 解析）

```powershell
uv pip install mineru
mineru-models-download --tier basic --source modelscope
mineru server start
```

`use_mineru = true` 时优先调用 MinerU，失败自动回退内置 `pypdf`。MinerU 4.x 档位：`flash` 仅提取文本（默认，无需完整引擎），`basic` / `standard` / `advanced` 需额外引擎支持。

## 启动

```powershell
python main.py
# 或
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

问答界面：http://127.0.0.1:8000/
接口文档：http://127.0.0.1:8000/docs

> 注意用 `127.0.0.1` 而不是 `0.0.0.0`，后者是监听地址，浏览器无法访问。
>
> Swagger UI 的 CSS/JS 已下载到 `static/swagger-ui/` 由本地托管（`/docs` 是自定义路由 + `/static` 静态挂载）。FastAPI 默认文档页依赖 `cdn.jsdelivr.net`，国内网络不可达时 HTML 能返回但脚本加载失败，页面就会白屏。`/redoc` 同样依赖 CDN，已一并关闭。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/init_data` | 加载 `knowledge_data` 入库，可重复执行，重复文档自动跳过 |
| POST | `/query` | 知识库问答，body: `{"question": "...", "strategy": "direct"}` |
| GET | `/docs_list` | 返回全部文档元信息 |

## 前端

访问 http://127.0.0.1:8000/ 使用问答界面。纯静态实现（HTML / CSS / 原生 JS），无构建步骤、无外部 CDN 依赖，由 FastAPI 通过 `/` 与 `/static` 直接托管：

- 对话式问答，气泡内展示分类、检索策略、耗时与来源文档
- 可展开「查看 N 条检索片段」，显示命中父块内容及向量 / 重排得分
- 左侧展示文档库状态（含入库状态色点），支持一键重新加载数据集
- 支持切换 `direct` / `hyde` / `subquery` / `step_back` 四种检索策略
- Enter 发送、Shift + Enter 换行，回答支持一键复制

`strategy` 可选：`direct`、`hyde`（假设问题）、`subquery`（子问题）、`step_back`（回溯问题）。

## 业务流程

1. `/query` 先用 `new_bert` 分类：`通用知识` 直接交 LLM 回答；`专业知识` 进入检索。
2. 检索策略调度生成查询（可选衍生新问题），BGE-M3 向量化后从 Milvus 召回子块。
3. 父块聚合去重，`score_threshold` 过滤低分片段，取 `retrieval_k` 条父文档。
4. `bge-reranker-v2-m3` 二次重排，取 `candidate_m` 条作为上下文。
5. LLM 严格依据上下文作答，无内容时回复「知识库无相关内容」，末尾附来源文档名称。

## 数据模型

MySQL `document_info`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| doc_id | BIGINT PK | 文档ID |
| doc_name | VARCHAR(255) | 文档名称 |
| upload_time | DATETIME | 入库时间 |
| file_type | VARCHAR(32) | 文件类型 |
| status | VARCHAR(16) | pending / processing / completed / failed |
| content_hash | CHAR(32) UNIQUE | 内容 MD5，用于重复校验 |

Milvus 集合同时存放父块与子块，字段：`pk`、`doc_id`、`parent_id`、`chunk_type`、`content`、`vector`。检索只命中 `chunk_type == "child"`，再按 `parent_id` 取回父块原文。

## 幂等说明

`/init_data` 以文件内容 MD5 判重：已 `completed` 的文档跳过；状态异常或内容变更的文档会先清理 Milvus 向量与 MySQL 记录再重新入库。若需强制全量重建，删除 MySQL 记录后重新调用即可。

## 注意事项

- **分类模型**：`models/new_bert` 由 `train_bert.py` 产出；若不存在则记录告警并把全部问题按 `专业知识` 处理（始终走检索）。
- **MinerU**：默认 `use_mineru = true`、`mineru_tier = flash`。代码会先执行 `mineru server start`（幂等），解析失败自动回退内置解析。
- **阈值**：`score_threshold` 基于归一化向量的 COSINE 相似度。实测相关片段约 0.70 ~ 0.82、无关片段约 0.35，默认 0.4 可有效区分。
- **Milvus 命名**：database / collection 名只允许数字、字母、下划线，代码会自动清洗非法字符并告警。集合使用 `Strong` 一致性，保证入库后立即可检索。
- **设备**：`device = cpu`，有可用 GPU 时可改为 `cuda`。
- **MySQL**：`[mysql] password` 需填本机实际密码；库 `e-commerce` 与表 `document_info` 在首次调用时自动创建。
