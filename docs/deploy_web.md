# 部署到公网（网页访问）

应用为 **FastAPI + PostgreSQL**：首页 `/`、API `/api/v1/*`、文档 `/docs`。

## 方式一：Docker Compose（自有服务器 / 云主机）

1. 安装 [Docker](https://docs.docker.com/get-docker/) 与 Docker Compose。
2. 在项目根目录创建 `.env`（可复制 `.env.example`），至少设置：

   - `FRED_API_KEY`：从 [FRED API Keys](https://fred.stlouisfed.org/docs/api/api_key.html) 申请。

3. 启动：

   ```bash
   docker compose up -d --build
   ```

4. 浏览器访问：`http://<服务器IP>:8000/`  
   换端口可设置环境变量 `HOST_PORT`，例如 `HOST_PORT=80 docker compose up -d`（Linux 上 80 端口可能需 root 或再加反向代理）。

5. 说明：

   - 容器启动时会执行 `init_db` 与一次全量采集；之后由应用内 **每小时调度**（`SCHEDULER_ENABLED=true`）更新。
   - 手动刷新：`POST /api/v1/jobs/ingest`（若配置了 `ADMIN_INGEST_KEY` 需带 `X-Ingest-Key` 或 `?ingest_key=`）。
   - 生产建议保持 `USE_SAMPLE_FALLBACK=false`（Compose 中已默认）。

6. HTTPS：在主机上用 **Caddy** / **Nginx** 做反向代理，申请 Let’s Encrypt 证书，将 `proxy_pass` 指到 `127.0.0.1:8000`。

## 方式二：Render / Railway / Fly 等 PaaS

通用步骤：

1. **新建 PostgreSQL** 托管数据库，复制连接串为 `DATABASE_URL`（需 `postgresql://...` 格式，与 `psycopg` 兼容）。
2. **新建 Web Service**，构建方式选 **Docker**，根目录指向本仓库；`Dockerfile` 已包含启动逻辑。
3. 在平台「Environment」中配置：

   | 变量 | 说明 |
   |------|------|
   | `DATABASE_URL` | 平台提供的 Postgres URL |
   | `FRED_API_KEY` | FRED 密钥 |
   | `USE_SAMPLE_FALLBACK` | 生产设为 `false` |
   | `SCHEDULER_ENABLED` | 设为 `true` 以启用每小时采集 |
   | `ADMIN_INGEST_KEY` | （可选）保护手动采集接口 |
   | `PORT` | 多数平台会自动注入，无需手写 |

4. **健康检查 URL**（若平台要求）：`GET /docs` 或 `GET /api/v1/rates/policy`。

注意：PaaS 若 **不提供持久磁盘**，仅依赖数据库即可；本应用状态在 Postgres 中。

## 方式三：仅本机演示公网访问（临时）

使用 [ngrok](https://ngrok.com/) 或 [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)，将本地 `uvicorn` 的端口映射到 HTTPS 子域名，适合演示，不适合长期生产。

## 部署后自检

- 打开 `/docs`，执行 `GET /api/v1/rates/latest?codes=FED_TARGET_UPPER,BOE_BANK_RATE,LPR1Y` 是否有数据。
- 查看 `GET /api/v1/jobs/ingest/latest`（若配置了 `ADMIN_INGEST_KEY` 需带密钥）确认最近一次采集统计。
