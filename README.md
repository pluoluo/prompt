# Prompt Portal

AI 图像提示词管理与优化平台，基于 GPT Image 2 结构化方法论。

## 鸣谢

案例库来源：[freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2)

## 功能

- **空间设计生成器** — 分类预设、动态参数、文字/JSON 自定义、多选、实时 JSON、浏览器保存进度，并可继续使用现有 AI 改写。预设库作为本地文件单独安装。
- **展台 / 展厅 / 文化墙专业预设** — 六套原创预设覆盖概念探索、原方案写实深化、立面设计及现场照片改造。通用要求使用短名称单选、多选，完整要求写入 JSON；项目名称、尺寸和准确文案保留填写。原始数据位于 `frontend/data/professional-presets.json`，可运行 `python tools/build_professional_presets.py` 重新生成。
- **模板库** — 分类筛选、关键词搜索、风格/场景标签多选
- **案例库** — 447 个 GPT Image 2 案例，中英文切换，图片懒加载
- **AI 优化生成** — 支持 DeepSeek Flash 等 OpenAI 兼容接口，多轮对话，模板改写/自由生成双模式
- **提示词撰写指南** — GPT Image 2 官方指南内嵌
- **在线编辑** — 模板/案例可编辑、删除，提交新模板
- **双语切换** — 分类/风格/场景/Prompt 中英文显示

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + uvicorn (Python 3.11+) |
| 前端 | Vue 3 CDN 单文件 SPA |
| 数据 | JSON 文件存储 |
| 代理 | nginx |
| AI | OpenAI 兼容文字接口，兼容旧 MiniMax 配置 |

## 生产环境部署

### 1. 克隆仓库

```bash
git clone git@github.com:pluoluo/prompt.git
cd prompt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

```env
API_KEY=your_api_key_here
Endpoint=https://your-provider.example/v1
LLM_MODEL=deepseek-flash
IMAGE_API_URL=http://localhost:8766
```

文字改写与图像反推优先使用同时配置的 `API_KEY` 和 `Endpoint`，模型默认 `deepseek-flash`，可通过 `LLM_MODEL` 修改。`Endpoint` 支持站点根地址、`/v1` 地址或完整 `/v1/chat/completions` 地址。图像反推会发送 JPEG、PNG 或 WebP 图片，通过图片描述与提示词整理两个步骤返回结果；所选接口和模型需要支持图片输入。配置修改后重启后端。未配置新接口时，兼容旧的 `MINIMAX_API_KEY` 及 MiniMax 图片理解接口。

### 3. 安装依赖

```bash
pip install fastapi uvicorn httpx python-dotenv
```

### 4. 同步案例库数据

首次部署需要同步案例数据和图片：

```bash
curl -X POST http://127.0.0.1:8768/api/gallery/sync
```

这会从 GitHub 拉取 cases.json 并下载所有案例图片（447 张，约 500MB）。

### 5. 启动后端 (systemd)

```bash
sudo cp prompt-portal.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable prompt-portal
sudo systemctl start prompt-portal
```

或直接运行：

```bash
./start.sh start
```

### 6. 配置 nginx

将 `nginx-portal.conf` 复制到 nginx 配置目录并加载：

```bash
# 复制配置文件
sudo cp nginx-portal.conf /etc/nginx/sites-available/prompt-portal
sudo ln -s /etc/nginx/sites-available/prompt-portal /etc/nginx/sites-enabled/

# 修改 root 路径为实际部署路径
sudo sed -i 's|/home/sahn/prompt|/your/deploy/path|g' /etc/nginx/sites-available/prompt-portal

# 测试并重载
sudo nginx -t
sudo nginx -s reload
```

### 7. 启动

```bash
./start.sh start
```

访问 `http://your-server:8769`。

### 8. 生成案例翻译（可选）

```bash
cd backend && python3 translate_prompts.py
```

## nginx 配置要点

- `proxy_read_timeout 300s` — AI 调用可能需要 60-120 秒
- `proxy_temp_path` — 指定 nginx 可写的临时目录
- `proxy_set_header Accept-Encoding ""` — 禁用 gzip 防止 Content-Length 不匹配

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/templates | 模板列表 |
| GET | /api/templates/{id} | 模板详情 |
| PUT | /api/templates/{id} | 更新模板 |
| DELETE | /api/templates/{id} | 删除模板 |
| POST | /api/templates/submit | 提交新模板 |
| GET | /api/categories | 分类列表 |
| POST | /api/match | AI 优化生成 |
| GET | /api/gallery | 案例库数据 |
| POST | /api/gallery/sync | 同步案例数据 |
| PUT | /api/gallery/cases/{id} | 更新案例 |
| DELETE | /api/gallery/cases/{id} | 删除案例 |
| POST | /api/gallery/cases | 新增案例 |
| GET | /api/gallery/translations | 案例翻译数据 |
| POST | /api/gallery/upload | 上传案例图片 |

## 环境变量

| 变量 | 说明 |
|------|------|
| MINIMAX_API_KEY | MiniMax API Key (AI 匹配必需) |
| IMAGE_API_URL | 图片生成服务地址 (可选) |

## 目录结构

```
prompt/
├── backend/
│   ├── main.py              # FastAPI 应用
│   ├── matching.py          # AI 匹配核心
│   ├── prompts_data.json    # 模板数据
│   ├── translate_prompts.py # 案例翻译脚本
│   └── data/
│       ├── gallery_data.json      # 案例元数据
│       ├── gallery_translations.json  # 案例翻译
│       └── gallery_images/        # 案例图片缓存
├── frontend/
│   └── index.html           # Vue 3 单文件 SPA
├── nginx-portal.conf        # nginx 配置
├── start.sh                 # 启动脚本
├── .env                     # 环境变量
└── README.md
```

## 空间设计生成器安装

前端新增“空间设计”导航，支持 `/static/index.html#space` 和 nginx 首页的 `/#space`。
“去生成图像”读取后端 `/api/config` 暴露的 `IMAGE_API_URL`，在新标签页通过 `prompt` 参数预填当前完整 JSON；不自动提交生图请求。目标应用需要支持此参数（本地 image-api 前端已支持）。
本地预设库位于 `frontend/data/space-presets.local.json`，该文件与参考图目录均被 Git 忽略。
仓库只包含生成器代码；导入的第三方文案和图片保留各自的来源及使用条件，不包含在本仓库的 MIT 授权中。

完整参数文件格式为 `{ "groups": { "分组编号": { "name": "分类", "presets": [{ "key": "预设编号", "name": "标题", "sections": { "分组名称": { "fields": { "字段名": { "label": "显示名", "type": "button-select", "options": [{ "label": "选项", "value": "完整提示词" }], "default": "完整提示词" } } } } }] } } }`。
支持 `button-select`、`select`、`multi-select`、`switch`、`boolean`、`text` 类型；预设无独立 sections 时使用分类的 sections。
没有安装服务端预设文件时，页面提供“选择预设文件”，可在当前页面载入完整参数 JSON。

将更新包解压到单独目录后，先检查目标项目（不会写入文件）：

```bash
python3 tools/install_space_generator.py --project-dir /实际部署目录/prompt
```

检查通过后增加 `--apply` 安装。工具会在目标项目 `.space-generator-backups/` 下备份被替换的文件，并在已有首页上应用小范围接入，保留其他本地修改；服务端配置、API 密钥、原模板库和案例库均不会被更新。
预设文件不在更新包内时可通过 `--library /路径/完整参数.json` 指定。生成器只使用 `preview.items[].localImage` 中的本地参考图路径，不热链第三方图片。
安装仅更新静态前端文件，不要求重启后端。刷新浏览器后打开“空间设计”入口。

基础检查：`node --test tests/space-core.test.cjs`。可用 `SPACE_PRESET_LIBRARY` 和 `SPACE_EXPECTED_PREVIEWS` 指定私有预设库与采集的默认结果，额外验证完整默认输出。

## License

MIT
