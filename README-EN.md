# ScenAgent (Mobile-Agent-v4)

[English](README-EN.md) | [中文](README-ZH.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)
![Platform](https://img.shields.io/badge/Platform-Android-green)

**ScenAgent** is the intelligent mobile agent testing framework , designed to achieve autonomous operation and task automation on mobile devices (Android) through Large Language Models (LLM) and multi-modal perception technologies. It integrates advanced screen perception, multi-agent collaborative planning, and reflection mechanisms to handle complex cross-application scenarios.

---

## 🌟 Core Values & Highlights

ScenAgent is not just an automation script; it is an agent system with **cognitive capabilities**:

*   **Autonomous Planning**: The `PlannerAgent` breaks down natural language instructions into executable subgoal sequences and dynamically adjusts them based on environmental changes.
*   **Precise Perception**:  Combining OCR, UI DOM tree models, and VLM to accurately identify text and icons on the screen. It supports two perception modes: VLLM and SoM (Set-of-Mark).
*   **Self-Reflection**: Compares screen changes after each operation to evaluate effectiveness and possesses error correction capabilities for path deviation or path error.
*   **Three Testing Modes**: Single-APP Single-Scenario, Single-APP Multi-Scenario, Multi-APP Multi-Scenario.
*   **Visual Interaction**: Provides a modern Web interface to monitor the Agent's thought process, operation trajectory, and screen state in real-time.

---

## 🚀 Features

- **Multi-Agent Architecture**: Includes four core agents: Planner, Executor, Reflector, and TaskJudge.
- **Dual-Modal Operation**: Supports direct coordinate-based clicking (VLLM) and marker-based positioning (SoM).
- **Three Testing Modes**: Single-APP Single-Scenario, Single-APP Multi-Scenario, Multi-APP Multi-Scenario.
- **Memory Mechanism**: Supports short-term task memory and long-term experience accumulation (Tricks).
- **Comprehensive Evaluation**: Built-in report generation system automatically produces test reports containing step details, screenshots, and success rates.

---
## ✅ Requirements

To ensure ScenAgent runs correctly, please prepare the following environment:

*   **Operating System**: 
    *   Recommended: Windows 10/11, macOS, or Linux (Ubuntu 20.04+).
*   **Programming Languages**: 
    *   **Python**: Version ≥ 3.10 (Required for latest type annotations and async features).
    *   **Node.js**: Version ≥ 16.x (Required only for developing or building the frontend).
*   **Device Tools**:
    *   **Android**: Install and configure `adb` (Android Debug Bridge) to ensure device connection via command line.
*   **Hardware**:
    *   NVIDIA GPU recommended if deploying local VLM/LLM, or ensure stable network access to online APIs like OpenAI/Qwen.

---

## 📥 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/likelikec/ScenAgent.git
cd ScenAgent
```

### 2. Install Python Dependencies

Using a virtual environment is recommended:

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Install Frontend Dependencies (Optional)

If you need to run the Web interface:

```bash
cd frontend
npm install
cd ..
```

---

## ⚙ Configuration

There are two key configuration files in the project root:

### 1. `test.json` (App & Scenario Definition)
Defines supported applications and specific test scenarios.

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

### 2. `run-config.json` (Task Flow)
Defines a sequence of tasks for batch execution.

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

## 💻 Usage

### Command Line Interface

Start tasks directly via `main.py`.

**Basic Usage:**

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

**Parameter Details:**

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--adb_path` | str | None | Full path to the Android Debug Bridge (ADB) executable. |
| `--api_key` | str | Required | API Key for the LLM service. |
| `--base_url` | str | Required | Base URL for the LLM service. |
| `--model` | str | Required | Model name to use (Recommended: `gpt-4o`, `qwen-vl-max` etc. with vision capabilities). |
| `--scenario_file` | str | `test.json` | Path to the JSON file defining test scenarios. |
| `--app_id` | str | None | Target App ID (Must be defined in scenario_file). |
| `--scenario_id` | str | None | Specific Scenario ID to run. |
| `--run_config` | str | None | Path to batch run configuration file for executing multiple tasks. |
| `--perception_mode` | str | `vllm` | Perception mode: `vllm` (Direct coordinates from vision model) or `som` (Set-of-Mark positioning). |
| `--output_lang` | str | `zh` | Language for logs and reports (`zh` or `en`). |
| `--planner_tricks` | str | `off` | Enable long-term memory/tricks library (`on`/`off`) to speed up common tasks. |

### Web Interface

Start the Web service for a visual experience.

1.  **Start Backend**:
    ```bash
    python web/server.py
    ```
    The service will start at `http://localhost:8000`.

2.  **Start Frontend** (Dev Mode):
    ```bash
    cd frontend
    npm run dev
    ```
    Access `http://localhost:5173` to open the console.

---

## 📊 Experimental Results

Below is a record of ScenAgent executing a real-world scenario.

**Task**: Move saved city list  
**App**: Cirrus (Weather App)  
**Goal**: Move "Shanghai" to the top of the list.

**Execution Overview**:

1.  **Open Sidebar**: Identified and clicked the menu icon in the top-left corner.
2.  **Enter Management Page**: Clicked the "Manage locations" option.
3.  **Drag/Verify**: Attempted to drag "Shanghai" up. The system detected that "Shanghai" was already at the top and intelligently determined the task was complete.

**Visual Process**:

| Step 1: Identify Menu | Step 2: Identify Entry | Step 3: Drag |Step 4: Verify |
| :---: | :---: | :---: |:---: |
| ![Step 1](output/T-Cirrus-Move%20saved%20city%20list-20260208_203412/images/screenshot_2026-02-08-74054-2e514262.png) | ![Step 2](output/T-Cirrus-Move%20saved%20city%20list-20260208_203412/images/screenshot_2026-02-08-74097-18bfdf37.png) | ![Step 3](output/T-Cirrus-Move%20saved%20city%20list-20260208_203412/images/screenshot_2026-02-08-74126-b1babe88.png) |![Step 4](output/T-Cirrus-Move%20saved%20city%20list-20260208_203412/images/screenshot_2026-02-08-74165-7ff60880.png) |
| *Action: Click (82, 173)* | *Action: Click (384, 718)* | *Action: Drag (540, 748) -> (540, 468)* |

**Final Result**: 
> Status: **Completed**  
> Duration: 2m 12s  
> Evaluation: The screenshot shows 'Shanghai' is already at the top of the list, goal achieved.

---

## 🤝 Contributing

Pull Requests are welcome!

1.  Fork the repository
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---

