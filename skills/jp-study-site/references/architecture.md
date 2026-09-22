# 架构与约束

- 浏览器：`website/dist/` 下手写 ES modules / CSS，hash 路由。这里也容纳被 Git 忽略的生成数据，不能把 dist 整个删除或全部打包。
- HTTP：`website/serve.py` 仅监听 loopback。`website/config.py` 管理连接开关和 CLI/Anki 配置；使用者自己的资料存在根目录 `study/`。
- Anki：`anki_sync.py` / `anki_calendar.py` 做只读快照与日历；`reviewer.py` 调用 `anki_addon` 原生复习器。评分必须由用户选择，重试不能重复评分。Anki 不运行时显示带时间的旧快照。
- 课堂：`classroom.py` 通过本机 CLI 与 `prompts/classroom-system.md`、`classroom-response.schema.json` 输出协议协作，后台持久化。教师不是可随意改学习文件的代理。
- 记忆：`classroom_memory.py` 校验引用，upsert/forget 形成有效投影；forget 不删除历史原话。
- 练习：`supplementary.py` 结合真实互动生成资格并保存补充题；TTS 技能 `skills/jp-listening-tts/SKILL.md` 显式注入上下文。TTS 目前依赖 macOS。
- 每日流程：`study_workflow.py` 保存 `study/daily-words/`、`daily-tasks/`、`progress/`。词单同日固定实际卡片；任务完成来自真实作答；五领域练习及隔日独立复测决定课次，错误可回退为待复测。
- 每日安排：`daily_preparation.py` 用来源指纹避免旧草稿覆盖新事实。`records_based` 是记录回退，`coach_prepared` 是实际教练发布。
- 前端：`study-dashboard.js` 对应任务/词单/课次/服务状态；`annotated-text.js` 处理显式日语边界；`pdf-reader.js` 内部翻页保留外层位置。Anki 轮询不得全页重绘或清空输入。
- 后台：`supervise.py`、`launch.py`、`scripts/start_site_background.py` 保持单实例及子服务恢复；不包含登录自启动或任何已注册的自动化。
- 备份：`scripts/backup_study.py` 保存学习文件和教师提示词，ZIP 哈希校验、仅恢复至空目录。不含 Anki 数据库/教材，未提供异地备份。

API：`/api/health`、`/api/system/status`、`/api/study-workflow`、`/api/lesson-progress`、`/api/daily-preparation`、`/api/learning-plan`、`/api/classrooms`、`/api/practice` 及 `/api/anki/*`。教材、词单、练习、课堂信息的调用方必须与数据协议一起检查。
