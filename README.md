# macapakka

从本地音频证据生成阿卡贝拉编配草稿的 agent 系统，使用 Prime Inference 完成编配与审校工具调用。

## 开发入口

- [`agent_system/`](agent_system/README.md)：当前系统源码、安装配置及运行说明。
- [`agent_system/vibacappella/`](agent_system/vibacappella/)：音频分析、编配、验证与导出。
- [`agent_system/tests/`](agent_system/tests/)：离线测试。
- [`agent_system/examples/prime.toml`](agent_system/examples/prime.toml)：Prime 配置。
- [`tools/`](tools/) 与 [`legacy/`](legacy/README.md)：打包工具和历史源码；部分工具需要仅存于本机的历史数据。

## 安装与检查

需要 Python 3.11 或更高版本：

```sh
cd agent_system
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

音频分析、渲染及字体依赖请按系统说明安装，不随仓库分发。

## Prime API Key

复制 `agent_system/secrets/prime.env.example` 为同目录的 `prime.env`，填写 `PRIME_API_KEY`。已有文件直接编辑。可选 `PRIME_MODEL` 和 `PRIME_TEAM_ID` 分别指定模型与计费团队。环境变量优先于文件值。

实际密钥、环境文件、录音、运行目录、实验结果、模型及本机依赖均不纳入版本控制。默认示例模型为 `z-ai/glm-5.3`；实际可用性及工具能力以 Prime 模型目录为准。生成作品仍需人工听审。

## 后续开发

此目录对应 GitHub 仓库 `Benzoin96485/macapakka`，后续修改在这里提交。测试与配置说明集中在 `agent_system/`。历史实验数据留在本机原位置，不随仓库上传。
