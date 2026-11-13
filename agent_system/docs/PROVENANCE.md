# 资料、继承代码与第三方依赖

核对日期：2026-11-13。

| 来源 | 用途与核对边界 |
|---|---|
| [MIT Parley 文档](https://parley-docs.mit.edu/) | 2026-11-13 已读取登录后 Chat Completions 和 Tool Calling 文档，确认 base URL、Bearer 鉴权与工具协议；尚未用真实 Key 调用 |
| [MIT Parley API 公告](https://orgchart.mit.edu/letters/parley-api-now-available-mit-community) | 确认是 MIT 的 API 服务，与其他同名 Parley 产品区分；不用于推断 endpoint |
| [Demucs 官方源码](https://github.com/facebookresearch/demucs) | 六轨分离 CLI 适配。该仓库已归档，维护状态应按官方说明判断；本项目未修改或捆绑它的模型 |
| [Basic Pitch 官方源码](https://github.com/spotify/basic-pitch) | `predict` / ONNX 音符候选适配；对分轨分别转写。使用其已安装模型，不捆绑权重 |
| [MuseScore 命令行文档](https://handbook.musescore.org/appendix/command-line-usage) | `-o` 导出。文档自身提示部分内容继承自 v3，实际能力需在所用 MuseScore 安装验证 |
| `../docs/TECHNICAL_REPORT_V3_ZH.md` | 本项目实际编曲与验证经验，不是外部出版总谱 |
| `../outputs/EYKM_Acappella_v3/source/render_samples.py` | 抽取并解耦 `SampleBank`，形成 `samples.py`；不再包含 EYKM 数据加载、路径与节拍硬编码 |
| 相邻 Claude 项目 `_work/scripts/v2_game.py` | 适配为 `game.py`，模型目录、语言和音频来自配置；不复制 GAME 模型权重 |

`proof.py` 是通用校样绘谱器；不是 MuseScore 渲染。`samples.py` 读取用户本地 SoundFont，覆盖本项目需要的采样区、包络和循环功能，并非完整 SoundFont 规范实现。五条人声的钢琴、Whistle 的长笛、VP 的鼓组预置是排练音色约定。

Demucs、Basic Pitch、GAME、ONNX Runtime、MuseScore、SoundFont 与字体分别受其自己的许可证约束；本包不声称取得或转授第三方模型、音乐、音库或字体的分发权。此记录不改变用户对已有原录音的使用授权。
