# 维护与发布

启动前确认 Python 3.10+；依赖和平台限制以根目录 README 为准。健康查询确认 `/api/health` 中的 service 是 `jp-study-local`，端口默认8766。服务已存在时不能重复起另一实例。Anki 和 Codex 由显式环境变量启用，演示默认关闭。

后台运行入口 `scripts/start_site_background.py`；日志在被忽略的 `tmp/`。重启前查看课堂 API 的任务状态，生成中不强行中断。静态文件变更无需重启。不要通过扩大网络监听或关闭安全校验解决启动问题。

## 验证

发布导出副本中运行 `python3 scripts/check_release.py`，它创建另一个隔离副本执行回归，不读取使用者的学习数据。相关独立检查包括 `check_study_workflow.py`、`check_daily_preparation.py`、`check_classroom.py`、`check_classroom_memory.py`、`check_supplementary.py`、Anki 系列检查及 `check_annotations.mjs`。CLI/TTS/真实硬件的验证须单独说明，不能把模拟通过当作已实测。

## 每日备课

`python3 scripts/prepare_daily_study.py --context` 读取事实，不计出席。生成 JSON 草稿仅含 source_fingerprint、date、headline（80字内）、guidance（700字内）；日期/指纹照抄上下文。顺序为 Anki → 课前练习 → 当前课，旧快照不冒充实时，词项预算不等于掌握数。

`python3 scripts/prepare_daily_study.py --publish-draft /path/to/draft.json --trigger scheduled` 校验并发布。读回 `study/daily-preparation/日期.json`；发生冲突重读一次，仍失败则保留现有安排。同日相同依据已存在 coach_prepared 时不重复写。没有预设调度，用户需要时再创建自己环境中的自动化，不能使用开发者私人 ID。

## 发布检查

以 Git 文件白名单检查，不依赖 `.gitignore` 一项措施：检查源码硬编码、生成目录、凭据格式、机器路径、课堂/Anki标识、个人统计、教材正文和 Git 历史。扫描输出仅位置/类型，不回显密钥。若有效密钥已泄露须轮换，不能只删当前文件。

每次优化同步源码、协议、测试、README、技能；可分享版保留每日词单、任务、课次证据、注音边界、后台恢复和备份，不恢复旧实现。只导出生成器及原创示例，重新在干净目录生成运行材料。私人数据、音频、书籍与备份均留在用户本机。

## 版本发布与截图

发布包由 `scripts/package_release.py --ref <tag> --output <empty-or-new-directory>` 从明确 Git 版本生成，包含源码包、配套技能包及 SHA-256。两类包都保留 LICENSE/NOTICE，技能包不携带私人配置或教材。截图仅允许来自隔离原创演示环境，显著标注演示，逐张目视核对；登记在 `docs/screenshots/manifest.json`，不要截用户正在学习的站点、浏览器地址栏或桌面。图片也属于发布检查范围。
