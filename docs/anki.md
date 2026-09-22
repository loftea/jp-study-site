# Anki 本机连接

需要用户自己的 Anki、AnkiConnect 与 JP 牌组。默认不开启，明确设置 `JP_ANKI_ENABLED=1` 后才连接。Anki 是排期和评分的唯一权威，网站不复制算法、不直接写数据库。

网站原生复习还需要 `website/anki_addon/` 中的组件：在 Anki 的“工具 → 插件 → 查看文件”定位自己的 addons21 目录，新建 `jp_website_review` 文件夹，把 `__init__.py` 和 `manifest.json` 复制进去，再重启 Anki。无需使用开发者机器路径。

组件依赖 AnkiConnect 的 `2055492159` 模块 ID 和 Anki 原生复习器内部接口，不保证所有 Anki 版本兼容。若不兼容，先在 Anki 中直接复习；不能通过绕过原生评分或直接写 SQLite 来修复。

网站评分只在用户显示答案并选择评分后发生。重复请求、过期卡片及不明确的提交结果有保护；不会自动替用户评分或触发 AnkiWeb 同步。升级组件前备份自己的 Anki。
