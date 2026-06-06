# ScenAgent

[English](README.md) | [中文](README-ZH.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)
![Platform](https://img.shields.io/badge/Platform-Android-green)

**ScenAgent** 是智能移动设备代理测试框架，旨在通过大语言模型（LLM）和多模态感知技术，实现对移动设备（Android）的自主操作与任务自动化。它集成了先进的屏幕感知、多智能体协同规划与反思机制，能够处理复杂的场景。

---

## 🌟 核心价值与亮点

ScenAgent 不仅仅是一个自动化脚本，它是一个具备**认知能力**的智能体系统：

*   **自主规划**: 通过 `PlannerAgent` 将自然语言指令拆解为可执行的子目标序列，并根据环境变化动态调整。
*   **精准感知**: 结合 OCR、UI DOM 树模型与 VLM，精准识别屏幕上的文本与图标，支持 VLLM 和 SoM (Set-of-Mark) 两种感知模式。
*   **自我反思**: 会在每一步操作后对比屏幕变化，评估操作是否有效，并具备路径偏离或者路径错误的纠正能力。
*   **三种测试模式**：单APP单场景，单APP多场景，多APP多场景。
*   **可视化交互**: 提供现代化的 Web 界面，实时监控 Agent 的思考过程、操作轨迹和屏幕状态。

---

## 🚀 功能特性

- **多智能体架构**: 包含 Planner（规划）、Executor（执行）、Reflector（反思）三类核心智能体。
- **双模态操作**: 支持基于坐标的直接点击（VLLM）和基于标记的定位操作（SoM）。
- **三种测试模式**：单APP单场景，单APP多场景，多APP多场景。
- **记忆机制**: 支持短期任务记忆与长期经验积累（Tricks）。
- **全面评估**: 内置报告生成系统，自动产出包含步骤详情、截图和成功率的测试报告。

---

## ✅ 环境要求

为了确保 ScenAgent 的正常运行，请准备以下基础环境：

*   **操作系统**: 
    *   推荐 Windows 10/11, macOS 或 Linux (Ubuntu 20.04+)。
*   **编程语言**: 
    *   **Python**: 版本需 ≥ 3.10，以支持最新的类型注解和异步特性。
    *   **Node.js**: 版本需 ≥ 16.x (仅在开发或构建前端界面时需要)。
*   **设备连接工具**:
    *   **Android**: 需安装并配置 `adb` (Android Debug Bridge)，确保能够通过命令行连接设备。
*   **硬件要求**:
    *   建议配备 NVIDIA GPU (如需本地部署 VLM/LLM)，或确保网络能够稳定访问 OpenAI/Qwen 等在线 API。

---

## 📥 安装指南

### 1. 克隆项目

```bash
git clone https://github.com/likelikec/ScenAgent.git
cd ScenAgent
```

### 2. 安装 Python 依赖

建议使用虚拟环境：

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. 安装前端依赖 (可选)

如果您需要运行 Web 界面：

```bash
cd frontend
npm install
cd ..
```

---

## ⚙ 配置说明

项目根目录下有两个关键配置文件：

### 1. `test.json` (应用与场景定义)
定义了支持的应用列表和具体的测试场景。

```json
{
  "apps": [
    {
      "id": "A1",
      "name": "Taobao",
      "package": "com.taobao.taobao",
      "launch-activity": "com.taobao.tao.welcome.Welcome"
    }
  ],
  "scenarios": [
    {
      "id": "S_SearchProduct",
      "name": "Search for a product",
      "description": "Open Taobao and search for 'iPhone 15'.",
      "extra-info": { "Input Data": "iPhone 15" }
    }
  ]
}
```

### 2. `run-config.json` (运行任务流)
定义了一次批量执行的任务序列。

```json
[
    {
        "app_id": "A1",
        "start_id": "S_SearchProduct",
        "end_id": "S_BuyProduct"
    }
]
```

---

## 💻 运行与使用

### 命令行模式

直接通过 `main.py` 启动任务。

**基本用法:**

```bash
python main.py \
  --adb_path "path/to/adb" \
  --api_key "YOUR_LLM_API_KEY" \
  --base_url "YOUR_LLM_BASE_URL" \
  --model "gpt-4o" \
  --scenario_file "test.json" \
  --app_id "A1" \
  --scenario_id "S_SearchProduct"
```

**参数详细说明:**

| 参数名 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `--adb_path` | str | None | Android Debug Bridge (ADB) 可执行文件的完整路径。 |  
| `--hdc_path` | str | None | HarmonyOS 设备控制命令 `hdc` 的路径。与 `--adb_path` 互斥，二选一。 |
| `--api_key` | str | Required | LLM 服务的 API Key。 |
| `--base_url` | str | Required | LLM 服务的 Base URL。 |
| `--model` | str | Required | 使用的模型名称 (推荐 `gpt-4o`, `qwen-vl-max` 等具备视觉能力的模型)。 |
| `--summary_api_key` | str | None | 摘要/翻译阶段使用的 API Key；不传时回退到 `--api_key`。 |
| `--summary_base_url` | str | None | 摘要/翻译阶段使用的 Base URL；不传时回退到 `--base_url`。 |
| `--summary_model` | str | None | 摘要/翻译阶段使用的模型名；不传时回退到 `--model`。 |
| `--coor_type` | str | `qwen-vl` | 坐标类型。通常保持默认即可；需要直接使用绝对坐标时可改为 `abs`。 |
| `--notetaker` | bool | `False` | 是否启用 Recorder/Notetaker。支持 `--notetaker`、`--notetaker true`、`--notetaker false`。 |
| `--perception_mode` | str | `vllm` | 感知模式：`vllm` (纯视觉模型直接输出坐标) 或 `som` (基于 Set-of-Mark 标记定位)。 |
| `--output_lang` | str | `zh` | 输出日志和报告的语言 (`zh` 或 `en`)。中文内容在任务结束后统一生成。 |
| `--print_device_cmd` | bool | `None` | 是否打印 ADB/HDC 设备命令。支持 `--print_device_cmd`、`--print_device_cmd true`、`--print_device_cmd false`；不传时按环境变量/配置决定，当前默认开启。 |
| `--scenario_file` | str | 自动回退到根目录 `test.json` | 包含测试场景定义的 JSON 文件路径。若不传且项目根目录存在 `test.json`，则自动使用它。 |
| `--app_id` | str | None | 目标应用的 ID (需在 scenario_file 中定义)。 |
| `--scenario_id` | str | None | 指定运行的单个场景 ID。 |
| `--scenario_start_id` | str | None | 指定批量运行时的起始场景 ID。 |
| `--scenario_end_id` | str | None | 指定批量运行时的结束场景 ID。 |
| `--run_config` | str | None | 批量运行配置。既可以是 JSON 文件路径，也可以直接传入 JSON 字符串。内容需为数组，每项至少包含 `app_id`，并可带 `start_id`、`end_id`、`scenario_id`/`specific_id`。 |
| `--run_dir` | str | None | 单次运行的输出目录；多场景运行时也可作为统一输出根目录。 |
| `--run_dir_prefix` | str | None | 多场景/批量运行时的输出根目录，系统会自动为每个场景创建子目录。 |
| `--device_id` | str | None | 指定目标设备序列号；多设备连接时推荐显式传入。 |
| `--planner_tricks` | str | `off` | 是否启用长期记忆/技巧库 (`on`/`off`)，用于加速常见任务。 |
| `--planner_tricks_topk` | int | `0` | 启用 `planner_tricks` 时，最多注入多少条历史技巧到 Planner。 |
| `--reflector_tree_check` | str | `off` | 是否启用基于 UI XML 树相似度的停滞检测 (`on`/`off`)；开启后仅在 Reflector 判断为 `C` 时触发额外检查。 |

补充说明：

- `--adb_path` 与 `--hdc_path` 不能同时传入。
- `--scenario_id` 与 `--scenario_start_id` / `--scenario_end_id` / `--run_config` 是不同的选择任务方式，通常只用其中一种。
- `--summary_*` 参数主要影响最终摘要、翻译和报告生成，不影响主执行链路的设备操作。

### Web 界面模式

启动 Web 服务以获得可视化体验。

1.  **启动后端**:
    ```bash
    python web/server.py
    ```
    服务将在 `http://localhost:8003` 启动。

2.  **启动前端** (开发模式):
    ```bash
    cd frontend
    npm run dev
    ```
    访问 `http://localhost:5173` 打开控制台。

### Docker / 云边协同部署

如果需要通过 Docker 在云服务器部署，并使用 FRP 连接本地 Windows 真机节点，请参考
[cloud-edge-notes/README.md](cloud-edge-notes/README.md)。

---

## 📊 实验结果示例

以下是 ScenAgent 在真实场景中的执行记录。

**任务**: Move saved city list (移动已保存的城市列表)  
**应用**: Cirrus (天气应用)  
**目标**: 将 "上海" 移动到列表的第一位。

**执行步骤概览**:

1.  **打开侧边栏**: 识别并点击左上角菜单图标。
2.  **进入管理页面**: 点击“管理位置”选项。
3.  **执行拖拽/验证**: 尝试将“上海”向上拖动。系统检测到“上海”已在第一位，智能判定任务完成。

**可视化过程**:

| 步骤 1: 识别菜单 | 步骤 2: 识别管理入口 | 步骤 3: 拖拽 |步骤 4: 验证 |
| :---: | :---: | :---: |:---: |
| ![Step 1](output/T-Cirrus-Move%20saved%20city%20list-20260208_203412/images/screenshot_2026-02-08-74054-2e514262.png) | ![Step 2](output/T-Cirrus-Move%20saved%20city%20list-20260208_203412/images/screenshot_2026-02-08-74097-18bfdf37.png) | ![Step 3](output/T-Cirrus-Move%20saved%20city%20list-20260208_203412/images/screenshot_2026-02-08-74126-b1babe88.png) |![Step 4](output/T-Cirrus-Move%20saved%20city%20list-20260208_203412/images/screenshot_2026-02-08-74165-7ff60880.png) |
| *Action: Click (82, 173)* | *Action: Click (384, 718)* | *Action: Drag (540, 748) -> (540, 468)* |

**最终结果**: 
> 任务状态: **Completed**  
> 耗时: 2分12秒  
> 评估: 截图显示 '上海' 已位于列表顶部，任务目标达成。

---

## 🤝 开发与贡献

欢迎提交 Pull Request！

1.  Fork 本仓库
2.  创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4.  推送到分支 (`git push origin feature/AmazingFeature`)
5.  开启一个 Pull Request

---
