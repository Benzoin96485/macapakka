# 数据契约与扩展接口

## 时间与来源

所有谱面音高使用实际发声音高的 MIDI 编号；Tenor 的八度谱号属于显示。每四分音符 480 ticks，当前编辑网格 120 ticks（十六分音符）。时间轴必须严格递增。

`evidence.json` 是一次 run 的固定分析输入，含原录音 SHA-256。若人工改了节拍、和声、器乐归属，使用 `--evidence` 开一个新 run，不能覆盖旧 run 的证据。

```json
{
  "schema_version": 1,
  "audio_sha256": "录音文件的实际 SHA-256",
  "duration_seconds": 2.0,
  "timing": {"anchors": [
    {"tick": 0, "seconds": 0.0},
    {"tick": 480, "seconds": 0.5},
    {"tick": 960, "seconds": 1.0},
    {"tick": 1440, "seconds": 1.5},
    {"tick": 1920, "seconds": 2.0}
  ]},
  "bars": [{"number": 1, "start_tick": 0, "duration_ticks": 1920,
            "numerator": 4, "denominator": 4, "section": "A"}],
  "notes": [{"id": "piano:0", "source": "piano", "instrument": "piano",
             "role": "candidate", "start": 0.0, "end": 0.5,
             "pitch": 64, "confidence": 0.7}],
  "drums": [{"id": "drums:0", "time": 0.0, "kind": "K", "strength": 0.8}],
  "harmonies": [{"id": "h:0", "start_tick": 0, "end_tick": 1920,
    "locked": true, "confidence": "reviewed_reference",
    "candidates": [{"symbol": "Cadd9", "pcs": [0,2,4,7],
                    "required_pcs": [2,4], "bass_pc": 0, "score": 1.0}]}],
  "alerts": ["音符置信值不是已校准的概率。"],
  "provenance": {"human_review": false}
}
```

上例是字段说明，不是完整旋律。真实样本在 `runs/demo-final/evidence.json`；可用 `demo.fixture()` 重新生成。

| 字段 | 含义 |
|---|---|
| `timing.anchors` | tick ↔ 原录音秒数的分段线性映射；支持自由速度，不使用一个全曲 BPM 硬套 |
| `bars` | 可逐小节变拍；短于拍号的首/尾小节允许作为弱起/结尾，需人工校订 |
| `notes[].source` | piano/guitar/bass/vocals/lead/backing/flute/other 等实际分析来源 |
| `role` | candidate / lead / backing / backing_candidate / flute；编配前的证据角色 |
| `instrument_confidence` | flute 归属阈值；不能只因“旋律在高音”就填写 1.0 |
| `syllable` | 可选的已对齐歌词音节；不是完整歌词 ASR 输入接口 |
| `harmonies[].locked` | 参考和声不可被 LLM 换成其他候选；校订必须产生新证据版本 |
| `required_pcs` | 实际声部必须出现的关键音高类，包含三音及决定色彩的七/九/sus 音等 |
| `bass_pc` | 根音或斜杠和弦低音 |
| `score` / `confidence` | 转写/检索的诊断量，不声称是正确率 |

## 事件谱

`score.json` 包含同样的 bars/timing、所选和声、七声部每小节事件，以及决策记录。事件至少有：

可选的 `source_roles` 保存 LLM 对人声候选的角色解释（lead/backing_candidate/ignore 与原因）。它仅能引用原有 vocals/lead/backing 候选，不改变音高、时刻或器乐身份；原始 evidence 不被覆盖。

```json
{
  "pitch": 64,
  "offset": 240,
  "duration": 480,
  "role": "piano",
  "source_ids": ["piano:0"],
  "velocity": 64,
  "confidence": 0.7,
  "syllable": "du"
}
```

`pitch: null` 是休止。offset 从当前小节起算，必须完整覆盖小节；工具会补上空隙休止。单个事件不跨小节，跨小节长音用同音高的 `tie_start`/`tie_stop`；MIDI/音频会合并延音，不重新起音。

来源音符允许八度重置，但不能保留原 source ID 又偷偷更改音高类。主唱和口哨必须有来源；`harmonic_support`、`editorial`、`vp_editorial` 是明确的编配创作。`vp_source` 关联鼓起音 ID。

VP 音节映射：K→36、pf→38、ka→37、t→42、ts→46、ksh→49、dm→45（GM MIDI）。每个人声/VP 声部单声，不能出现重叠事件。

## 添加工具/模型

1. 在本地分析 worker 新增适配器，输出上述 `notes` / `drums` / 时间映射。不要让模型输出直接写最终 MusicXML。
2. 新增编配工具时，在 `agent.py` 的 `SCHEMAS` 声明 schema，并在 `MusicTools` 绑定对应方法。工具通过 `save()` 保存版本；不能向 LLM 暴露任意 shell、网络 URL 或文件路径。
3. 新 provider 实现 `complete(messages, schemas) -> assistant_message`，保持标准化 `tool_calls`。不要绕过持久化预算、密钥处理和重试限制。
4. 新音轨引擎读取同一 `sound_events()`，正确处理延音与时间 anchors；导出后检查真实文件。不能在失败时静默替换成振荡器并继续称为指定采样引擎。
5. 新谱面功能先扩展 canonical schema、校验器与 MusicXML/MIDI 反向核对，再扩展 PDF 渲染。

## run 文件

- `input/`：原文件快照；`work/`：统一 WAV、分轨、转写缓存。
- `evidence.json`：固定候选证据；`score.json`：当前事件谱。
- `revisions/`：事件谱修订；`agent/`：两个角色每个窗口的消息检查点。
- `events.jsonl`：工具输入、结果与阶段事件；`budget.json`：跨恢复累计的 API 预算。
- `validation.json`：音乐结构检查；`exports/revision-N/`：总谱、音轨、审听页、审校记录、manifest。
- `state.json`：created → analyzing → analyzed → arranging → exporting → exported_draft_needs_review；异常进入 failed，并保留前面产物。
