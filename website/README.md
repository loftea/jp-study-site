# 网站实现

安装、导入、运行与能力边界见 [项目 README](../README.md)。架构见 [配套技能参考](../skills/jp-study-site/references/architecture.md)。

`dist/` 中的 JS/CSS/HTML 是手写源码；其中 data/reading/audio/images 是生成材料，默认不进入 Git。课堂 schema 与 system prompt 位于 prompts/，更新协议时须同时检查后台和前端。

## 课堂与复习修复

- 教练默认固定为 `gpt-6.1-sol` / `medium`，新课和续课均显式传参；单轮 CLI 超时为600秒（10分钟）。超时保留原消息并可重试；课后音频合成有独立超时。
- 课堂本地音频链接显示播放器及备用链接，仅接受受限本地路径。
- Anki负责读音、词义回忆和间隔复习；课堂负责句型、课文和情境运用。
- 缺少 JP Website Review Bridge 时显示明确安装提示。设备迁移需安装 AnkiConnect 和网站复习组件，并重启 Anki。
- 新增检查：`python3 scripts/check_classroom_model.py`、`node scripts/check_classroom_text.mjs`；Anki连接错误回归在 `scripts/check_anki_review_ui.mjs`。测试不创建正式课堂或修改学习成绩。
