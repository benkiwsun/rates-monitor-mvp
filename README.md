# Rates Monitor MVP

基于“利率传导 + 金融板块分析框架”的利率监测网站 MVP。

## 已实现内容

- API：
  - `/api/v1/rates/*`
  - `/api/v1/spreads/*`
  - `/api/v1/alerts/*`
- 首页线框：
  - KPI 卡片
  - 主图占位
  - 告警面板
  - 热力图/曲线模块占位
- 交付文档：
  - 数据库表结构
  - API 清单
  - 首页线框图
  - 两周开发排期

## 目录结构

```text
rates-monitor-mvp/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── sample_data.py
│   │   ├── templates/index.html
│   │   └── static/style.css
│   └── sql/schema.sql
├── docs/
│   ├── database_schema.md
│   ├── api_catalog.md
│   ├── homepage_wireframe.md
│   └── mvp_two_week_plan.md
└── requirements.txt
```

## Streamlit 部署（推荐快速上线仪表盘）

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

详细（含 Streamlit Community Cloud、Secrets、外部 Postgres）：[docs/deploy_streamlit.md](docs/deploy_streamlit.md)。Secrets 示例见根目录 **`streamlit_secrets.example.toml`**。

## 部署到公网（Docker / 云主机 / PaaS · FastAPI）

见 [docs/deploy_web.md](docs/deploy_web.md)。最快路径：装好 Docker 后在项目根执行 `docker compose up -d --build`，浏览器访问 `http://<主机>:8000/`。

## 运行方式

```bash
pip install -r requirements.txt
copy .env.example .env
python -m backend.scripts.init_db
python -m backend.scripts.ingest_rates
uvicorn backend.app.main:app --reload
```

打开：

- 首页：`http://127.0.0.1:8000/`
- Swagger：`http://127.0.0.1:8000/docs`

## 真实数据接入说明

- `FRED`：通过 `FRED_API_KEY` 拉取美债、SOFR/EFFR及部分政策利率时间序列。
- `央行官方接口`：
  - ECB：`data-api.ecb.europa.eu`
  - BoC：`bankofcanada.ca/valet`
- 其余央行已预留 provider 架构，可继续按同模式扩展。

## PostgreSQL 持久化

- API 默认优先从 PostgreSQL 读取。
- 当库中无数据且 `USE_SAMPLE_FALLBACK=true` 时，自动回退样例数据，便于本地开发。
- 生产建议设置 `USE_SAMPLE_FALLBACK=false`。

## 下一步建议

- 扩展更多央行官方数据接口（BoE/BoJ/SNB/RBA/PBoC）
- 前端升级到 Next.js + ECharts（替换当前线框模板）
- 增加告警任务调度与邮件/企业微信推送
- 增加周报自动生成与回测模块
