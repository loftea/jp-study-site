---
name: jp-listening-tts
description: 为本地标日网站课堂准备有真实学习依据的课后听力补充题，通过结构化合成稿调用网站的 macOS 日语 TTS 服务。课堂下课生成补充练习时使用。
---

# 课堂听力与本地合成

网站每轮通过 context.listening_tts_skill 注入本技能，无需老师使用文件或终端工具。老师输出合成稿，后台调用本机 Kyoko 日语声线（155 语速）生成 PCM WAV，与课堂一起保存。只在 kind=finish 且 context.supplement_eligible=true 时生成新的 supplementary_exercises；其他时候返回空数组。

- 依据本课堂学生实际练习的词句、错误和问题，编写 3–6 道原创迁移题（最多 8 道），其中至少一道听力。每题引用实际用户消息的 evidence_message_id 和原文 quote，topic 说明学习目标。听力用已教词汇，短句和单一清楚情境，不引入未解释的高级语法。
- written 题填写 prompt、answers（可接受的简洁答案）、target（注音参考答案）、explanation。transcript 和 tts_text 留空。
- listening 题的 prompt 只含作答要求及问题，不能提前泄露原文或答案。填写完整 transcript（汉字附平假名），tts_text 只填需要朗读的日语假名和标点。不要在 tts_text 中写汉字、注音括号、中文说明、网址、SSML 或 shell 命令。
- tts_text 必须忠实对应 transcript；助词「は」「へ」按实际声音写「わ」「え」。数字和多音字在此写正确假名。保留适当标点停顿，不靠重复字符模拟语速。避免多个角色需要不同声音的题：当前引擎只有一个声线。
- 听力考察听后提取信息或动作顺序，不只让学生抄写。允许中文答意；参考答案包括合理简短形式。答案解释所有日语汉字都附平假名。
- 这是原创合成音频，不是教材原音或真人录音。老师不负责生成路径，不声称已播放、亲耳验收或已写入成功；网站展示实际音频状态。合成失败不丢弃题目，网站可重试音频。
- 原文和参考答案默认折叠。看过原文后作答记为 transcript_viewed，不能标为盲听；文字转写不能用于评价发音。已生成的练习再次打开不重新出题、不覆盖旧答案。

存储：study/classrooms/<课堂ID>.json 的 supplement；音频在 study/classrooms/audio/<课堂ID>/；作答在 study/practice/website-responses.jsonl，通过 session_id 与 exercise_id 关联课堂。网站按香港日期显示今天的补充练习，往日练习从学习记录回看。

分发本技能时保留仓库 LICENSE 和 NOTICE；本技能采用 PolyForm Noncommercial 1.0.0，未授予商用许可。
