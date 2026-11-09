# 网页试玩与 Cloudflare 自动发布

`develop` 已包含网页正式界面（ZRS）与两个剧本的完整试玩，可构建并做部署预检。Cloudflare 项目由 ZC 管理；成员日常只需按协作流程提交 PR，不需要 Cloudflare 账号。

## 1 本地打开

Python 3.10+；Node.js 使用根目录 `.node-version` 指定的 24.22.1（最低 22.18）。网页依赖与 Python 核心分开。

在 VS Code 打开仓库，在终端运行：

```bash
npm ci
npm run dev -- --open
```

浏览器打开后可选择剧本，点击选项、使用／组合道具、指认、保存／读取进度及导入／导出 JSON。存档在当前浏览器中，每个故事一个槽；请点击“保存进度”。换设备时先导出。开发服务器结束后网页停止服务；Cloudflare 部署后不依赖任何成员的电脑。

## 2 发布分支

- Cloudflare 项目 `taleloom` 已连接本仓库（Workers Builds）。
- **正式网址**：<https://taleloom.zoranzhou.com>（自定义域名，生产和预览都已开启；<https://taleloom.zoranzhou28.workers.dev> 同样可用）
- **生产分支**：当前为 `develop`（2026-11-08 起），PR 合入 `develop` 后自动部署；从 `develop` 向 `main` 的发布 PR 合并后改为 `main`。只有一个同名项目，不要另建。
- **非生产分支**（成员分支）：构建并部署以分支命名的预览（Worker Preview），网址为 `<预览名>.taleloom.zoranzhou.com`，同时有 workers.dev 预览网址；不切换正式网址。预览名取自分支名，`/` 换成 `-`，例如 `zc/custom-domain` → <https://zc-custom-domain.taleloom.zoranzhou.com>。同一分支再次推送会更新同一个预览网址。
- 改生产分支只在 Cloudflare 控制台 **Settings → Build → Branch control** 中操作；Worker 的其他设置一律改 `cloudflare.config.ts`（见 2.1）。

### 2.1 Worker 配置同步（2026-11-08 已完成）

**状态**：2026-11-08 已由 ZC 在本机完成一次同步部署，远端配置与 `cloudflare.config.ts` 一致，网址 <https://taleloom.zoranzhou28.workers.dev>。以下记录原因和做法，供以后重建 Worker 时参考。

**已知问题（2026-11-07 首次构建）**：测试、校验、回放、网页构建与预检全部通过，但 `npm run deploy` 中止，日志为 `Aborting the upload operation because of conflicts`。原因：Worker 是在控制台创建的，控制台上的配置（未启用静态资源、`workers_dev`／`preview_urls` 关闭、兼容日期 2026-11-07、日志与追踪开启）与仓库 `cloudflare.config.ts` 不同。当前 `cf` CLI 的 `deploy` 与 `versions upload` 在非交互环境中固定使用严格模式（源码中 `strict: true`，没有关闭参数），只要远端与本地配置不同就拒绝上传，所以云端构建永远无法完成第一次部署。

解决办法：由有 Cloudflare 账号权限的成员（ZC）在本机交互式部署一次，让远端配置与仓库一致。之后云端每次构建都能直接部署。

```bash
npm ci
npx cf auth login                      # 浏览器中登录 Cloudflare
npm run build
npx cf deploy --prebuilt --mode production
```

交互模式会列出同样的配置差异并询问是否覆盖，确认即可。完成后：

- 在 Cloudflare 控制台对 `taleloom` 的最新提交点 **Retry build**，确认 Build 与 Deploy 都成功，打开 `workers.dev` 地址试玩。
- **以后不要在控制台修改该 Worker 的设置**（兼容日期、workers.dev、预览链接、日志等），一律改 `cloudflare.config.ts` 并走 PR；否则严格模式会再次拦下部署。

## 3 Cloudflare 页面逐项填写

在 **Workers & Pages → Create application → Import a repository / Connect Git** 选择 GitHub，授权 `zoran-sid/TaleLoom`。选择 **Workers**。

| 字段 | 值 |
| --- | --- |
| Repository | `zoran-sid/TaleLoom` |
| Worker / Project name | `taleloom` |
| Production branch | `main`（需要先包含本实现） |
| Root directory | 仓库根目录，留空或 `/` |
| Build command | `npm run build:cloudflare` |
| Deploy command | `npm run deploy` |
| Non-production branch deploy command | `npm run deploy:preview` |
| Build variable `PYTHON_VERSION` | `3.12` |
| Build variable `SKIP_DEPENDENCY_INSTALL` | `1`（安装已包含在构建命令中） |

Node 版本由 `.node-version` 读取，也可在 Build variables 填 `NODE_VERSION=24.22.1`。这条路线无需填写 Pages 的 output directory。`cf build` 自动生成 `.cloudflare/output/v0/`，部署命令直接发布经过构建和预检的这份产物。Cloudflare 已设置的 `PLAYWRIGHT_BROWSERS_PATH=0` 可以保留；当前云端构建不使用它。

开启非生产分支构建，至少纳入 `develop`；成员分支按需纳入。还没有合入网页配置的旧成员分支先保持原有 GitHub 模块测试，更新到新版 `develop` 后再开启网页预览。构建环境可以访问仓库；不要把 Cloudflare token 放进前端环境变量或源码。使用 Git 集成创建／管理的构建授权。

Cloudflare 构建依次运行：锁定依赖安装 → 全部 Python 测试 → 剧本校验 → 全部回放 → 静态网页打包 → 部署预检。上述任一步失败都不执行部署，构建日志保留失败原因。

真实 Chromium 验收由 GitHub Actions 的 `web (build + browser + deploy dry-run)` 检查运行，完整覆盖浏览器通关、存档和错误处理。Cloudflare 构建环境不允许安装器通过 `su` 获取管理员权限，因此浏览器及其 Linux 系统依赖在 GitHub 的 Ubuntu runner 中安装。合入 `develop`／`main` 前须确认包括 `web` 在内的全部 GitHub 检查通过；正式开通时将这些检查加入分支保护的必需状态检查。Cloudflare 原生 Git 构建与 GitHub 检查并行，不会等待 GitHub；临时直接部署功能分支时，应在其 GitHub 检查通过后验收试玩网址。

当前非生产命令用 `cf previews deploy` 部署以分支命名的预览：自定义域名上为 `<预览名>.taleloom.zoranzhou.com`，workers.dev 上为 `<预览名>-taleloom.zoranzhou28.workers.dev`，不切换正式流量。自定义域名在 `cloudflare.config.ts` 的 `domains` 中声明（生产与预览均开启），必须与控制台一致。生产命令 `cf deploy` 才更新正式版本。Cloudflare CLI 和 Vite 插件目前为 beta，仓库锁定已验证版本，升级须重新验收。

## 4 首次发布验收

- 等待第一次 Build 与 Deploy 都成功，打开控制台给出的 `workers.dev` 地址。
- 分别进入两个故事，完成一次行动、存档、刷新继续；用手机宽度检查选项和笔记。
- 推送非生产分支后打开 `<预览名>.taleloom.zoranzhou.com`，确认正式地址保持原版本。
- 后续通过发布 PR 更新 `main`，核对部署提交号与固定网址的新版本。
- 若构建失败，查看日志并修复；保留当前成功版本，继续使用相同发布流程。

发布前可本地执行完整验收（不需要 Cloudflare 登录）：

```bash
npm ci
npx playwright install chromium
npm run check:deploy
```

有管理员权限的 Linux 本地环境或 GitHub CI 使用 `npx playwright install --with-deps chromium` 安装系统依赖。Cloudflare 使用上表的 `npm run build:cloudflare`，不安装或启动浏览器；本地与 GitHub 的 `npm run check:deploy` 继续执行全部浏览器测试。

## 5 与成员任务的边界

| 模块 | 当前部署基础 | 正式模块如何接入 |
| --- | --- | --- |
| Python 核心、加载、校验、解析、存档、剧本 | 复用现有文件；没有修改这些文件 | 各成员继续原任务 |
| 会话 | `taleloom/legacy_session.py` 包装现有 v0 Engine；桌面与网页都经 `taleloom/session_factory.py` 创建会话 | ZQO 实现 `taleloom/session.py` 后，在 `taleloom/session_factory.py` 显式切换；先通过接口及回放测试 |
| 运行桥接 | `web/runtime/bridge.py`、`worker.js`、`client.js` | ZC 维护 JSON 消息和后台 Python；ZRS 可直接使用 `GameClient` |
| 界面 | 根目录 `index.html` 加载 `web/ui/`、`web/styles/`（ZRS，PR #9） | ZRS 维护；桌面界面在 `taleloom/gui/` |
| 存储 | `web/preview/storage.js` 单槽 localStorage（临时，`web/ui/app.js` 引用）；兼容既有 v1 JSON | LQ 交付 `web/storage/` 和纯数据编码器后替换；不占用其正式文件 |
| 构建／发布 | `tools/build_web.py`、配置文件、新增 `web.yml` | ZC 维护；原 `checks.yml` 保持原样 |

当前适配支持现有场景选择、线索、指认、使用与组合道具；深空序章的氧气显式列为公开资源。新插件、新资源显示、随机与文本变体由正式模块按契约接入并补测试；不会自动把全部内部变量或配方显示给玩家。原剧本中的少量 CLI 操作提示在展示层转换为按钮说明，剧本 JSON 保持原样。

游戏包使用显式白名单，包含所需 Python 模块和 `story.json`，排除桌面界面、测试、攻略、存档、环境文件和部署凭据。新增正式模块时，ZC 同步 `tools/build_web.py` 的 `CORE` 列表。当前未打包可选图片／音效，素材阶段再按允许的类型与路径接入。

独立验证入口：

```bash
python3 -B -m unittest tests.zc.test_web_session tests.zc.test_web_build
python3 -B -m unittest tests.integration.test_web_playthroughs
npm run build
npm run test:web
```

`tools/web_vectors.py` 从团队维护的通关脚本生成图形操作，逐步比对原生引擎与会话状态；浏览器再次执行这些操作并比较存档，包括指纹。新增不受支持的动作会使发布检查失败，提醒先完成对应图形操作。

## 6 工具与来源

- [Workers Builds 配置](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/)：原生 Git 集成和构建命令。
- [构建分支](https://developers.cloudflare.com/workers/ci-cd/builds/build-branches/)：生产与非生产构建。
- [构建镜像](https://developers.cloudflare.com/workers/ci-cd/builds/build-image/)：Node／Python 版本变量、依赖安装设置和 Ubuntu 环境。
- [Cloudflare CLI 构建与部署](https://developers.cloudflare.com/cf/projects/)：`--prebuilt --mode production`、无上传预检及分支预览（`cf previews deploy`）。
- [Pyodide Web Worker](https://pyodide.org/en/stable/usage/webworker.html)：模块型 Worker 运行 Python；运行时文件随网站自托管。

运行时版本和许可证见 `web/runtime/THIRD_PARTY_NOTICES.txt`，依赖及完整性校验固定在 `package-lock.json`。网页不从第三方 CDN 下载运行时，不需要在线 Python 服务器。
