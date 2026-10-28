# Taurus AI 3.0：Mac 更新、测试与 GitHub 发布指南

**这次是完整项目更新，保留你原先的 Logo。新版 ZIP 不包含密钥、虚拟环境或 Git 仓库历史，不会删除你电脑上的 `.streamlit/secrets.toml`。不要把密钥复制到 GitHub。**

## 1. 在旧项目里建立安全分支

首先在 PyCharm 的 Terminal 输入：

```bash
cd /Users/zoumengzhao/PycharmProjects/stock-intelligence-dashboard
git status --short
git branch --show-current
git ls-files -- .streamlit/secrets.toml .env
```

- 第三条命令必须**没有输出**。如果列出了 `secrets.toml` 或 `.env`，**停止操作**，先解除文件追踪并轮换泄露密钥。
- 如果 `git status --short` 有内容，先保存当前工作：只添加你确认安全的源码文件并提交。不要盲目把密钥加入 Git。
- 工作区干净后创建测试分支：

```bash
git switch -c taurus-v3
```

如果提示该分支已经存在，改用 `git switch taurus-v3`；如有尚未提交的修改，先处理它们。

## 2. 解压完整更新包

先将下载的 `taurus-ai-v3-complete.zip` 放到 Mac 的「下载」文件夹，再运行：

```bash
cd /Users/zoumengzhao/PycharmProjects/stock-intelligence-dashboard
unzip -o ~/Downloads/taurus-ai-v3-complete.zip -d .
```

这是完整覆盖代码（`app.py`、数据模块、图表模块、测试等），**不是解压到新的子文件夹**。它不包含你的 API Key 文件。

## 3. 安装依赖并运行自动化测试

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python i18n.py --check
.venv/bin/python -m unittest discover -s tests -v
```

预期最后看到 `OK`。如果提示 `.venv/bin/python: No such file or directory`，根据项目中的虚拟环境目录改用 `venv/bin/python`，或在 PyCharm 里使用已经配置好的解释器。

这些是**离线模拟测试**，不使用真的 Groq 密钥或 Yahoo 行情。因此通过自动化测试以后，还要手动打开网站检查真实接口。

## 4. 在 Mac 上运行新版本

```bash
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

浏览器打开：http://localhost:8501 。停止运行按 `Control + C`。

### 必须人工验收的操作

1. 点「全球市场」；切换美股、中国 A 股、港股、欧洲，确认都不是空白页；点某只股票能跳转正确股票。
2. 在 A 股找贵州茅台（`600519.SS`）、宁德时代（`300750.SZ`）；港股找腾讯（`0700.HK`）、阿里巴巴（`9988.HK`），检查是否有公司名称。
3. 研究 `AAPL`，选择 `1M、3M、6M、1Y、5Y`，使用图表缩放/拖拽，观察日期与真实已加载的 K 线是否相匹配。
4. 打开「指标参数」，将 RSI 14 改成 9；检查 RSI 曲线和数值发生变化。切换 MACD、Volume、ATR、KDJ。
5. 点击顶部「AI 研究」，从该页面生成报告和追问，确认不会错误地跳回股票研究。
6. 切换简体中文、English、Deutsch；打开新闻、财务页面；缩窄浏览器看看手机排版。
7. 如果某只股票缺少数据，检查页面是否显示错误说明，而不是全站无法加载。

## 5. 保存并上传 GitHub 的测试分支

**必须在 `taurus-v3` 分支上，且手动测试通过**，再执行：

```bash
git branch --show-current
git ls-files -- .streamlit/secrets.toml .env

git add .gitignore .streamlit/config.toml README.md UPDATE_GUIDE_ZH.md RELEASE_TEST_REPORT.md \
  ai_analysis.py app.py assets/style.css assets/taurus-mark.svg charting.py \
  i18n.py indicators.py main.py market_data.py news_data.py presentation.py \
  research_snapshot.py ui_labels.py requirements.txt tests/test_project.py tests/test_app_smoke.py

git --no-pager diff --cached --name-only
git commit -m "Taurus AI 3.0 tested research upgrade"
git push -u origin taurus-v3
```

`git --no-pager diff --cached --name-only` **绝对不能**列出 `.streamlit/secrets.toml`、`.env` 或其他私密文件。否则停止提交并先排除。提示 `nothing to commit` 表示内容此前已提交；可以继续推送。`git push` 只上传开发分支，不会立即覆盖线上 `main`。

## 6. 合并到正式网站（不会强行覆盖 GitHub 的 main）

浏览器打开你的 GitHub 仓库：

https://github.com/zmzpoi/stock-intelligence-dashboard

进入 **Pull requests → New pull request**，选择：

- **base: main**（正式网站）
- **compare: taurus-v3**（这次更新）

核对修改清单后，点击 **Create pull request**，再点击 **Merge pull request**。如果 GitHub 提示冲突，**不要强行合并，不要使用 `git push --force`**；应先解决冲突。

假如 Streamlit Cloud 连接的就是这个仓库的 `main` 分支，合并后它会检测代码变更并自动重新部署。可以在 Streamlit Cloud 的应用设置中确认仓库、分支及入口文件是否仍指向 `main` / `app.py`。

## 7. Streamlit Cloud 的新 Groq Key

注意：**GitHub 不需要、也不应该保存 Groq Key。**

到 https://share.streamlit.io/ 打开 Taurus AI → **Settings → Secrets**，把原有内容中的密钥更新为：

```toml
GROQ_API_KEY = "这里填写你自己的真实新密钥"
```

保存（Save）。若云端仍提示找不到密钥，尝试应用菜单中的 Reboot。请不要把密钥发到聊天、截屏或复制进公开文件里。云端密钥与本地 `secrets.toml` 是两个独立设置。

## 8. 失败时怎么办

- `git push origin main` 出现 `non-fast-forward`：不使用 `--force`；按上面步骤使用测试分支和 Pull Request。
- 自动测试出现 `FAIL` / `ERROR`：不要发布，先检查详细报错。
- 网站能打开，但某只股票显示无行情：可能是 Yahoo 数据源不可用；先用 `AAPL` 和 `600519.SS` 对比。
- `AI` 提示密钥错误或 429：核对本地或 Cloud Secrets，检查 Groq 账户限流与权限。
- 图表仍出现长空白日期：记录股票代码、所选时间窗口、最后一个可用交易日和屏幕截图；本版不会虚构历史行情，也不能拉取数据提供商没有返回的日期。

这是一个依赖免费第三方数据源的教育研究应用，不是保证实时的交易系统。
