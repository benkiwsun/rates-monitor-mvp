# Streamlit 部署说明

入口文件：**`streamlit_app.py`**（仓库根目录）。

## 本地运行

```bash
pip install -r requirements.txt
# 配置 .env 或 .streamlit/secrets.toml（见 streamlit_secrets.example.toml）
python -m backend.scripts.init_db
python -m backend.scripts.ingest_rates
streamlit run streamlit_app.py
```

浏览器默认：`http://localhost:8501`

## Streamlit Community Cloud

1. 在 GitHub 上推送本仓库（或 Fork 后连接 Cloud）。
2. [share.streamlit.io](https://share.streamlit.io) → New app → 选择仓库与分支，**Main file path** 填：`streamlit_app.py`。
3. **Secrets**：在 App settings → Secrets 中粘贴 TOML，参考仓库根目录的 **`streamlit_secrets.example.toml`**。至少需要可用的 **`DATABASE_URL`**（推荐使用 [Neon](https://neon.tech)、[Supabase](https://supabase.com) 等托管 PostgreSQL；Streamlit Cloud 本身不提供 Postgres）。
4. **`FRED_API_KEY`**：建议填写，否则美国收益率等 FRED 序列可能为空。
5. 首次部署后，在应用侧栏点击 **「全量采集」** 写入数据；或在本地/CI 对同一数据库执行 `python -m backend.scripts.ingest_rates`。

注意：Streamlit Cloud 对单次脚本执行有超时限制，若采集过久失败，请在网络稳定的环境对同一 `DATABASE_URL` 先跑一遍 `ingest_rates` 再打开应用。

## 与 FastAPI 版本的关系

- **Streamlit**：本文件，适合分享仪表盘与快速查看。
- **FastAPI**（`uvicorn backend.app.main:app`）：REST API + 原首页模板；可与 Streamlit 共用同一数据库。
