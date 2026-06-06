# 批量并行跑测试

独立脚本，按你在脚本顶部写好的「设备 -> app」映射并行跑（每台手机一个子进程，
不同设备并行，同一设备内的多个 app 顺序跑）。**不依赖也不修改 web 后端**；
请勿在后端服务运行时同时执行（会争抢设备）。

> 所有参数都摊在 `run_batch.py` 顶部，**直接改脚本即可**，不需要记环境变量。

---

## 一行启动（Windows PowerShell）

```powershell
& "E:\anaconda\envs\mobile-agent\python.exe" batch_runner\run_batch.py
```

- 必须用 **conda 环境内的 python.exe** 启动（**别用 `conda run`**，它会损坏中文 argv 并按 GBK 崩溃）。
- 启动本脚本的那个 python 就是 `PYTHON`（用来跑 main.py），所以上面这台 python 要是 `mobile-agent` 环境的。
- 脚本会自动给每个子进程设 `PYTHONUTF8=1`，中文路径/输出不会崩。

---

## 怎么改脚本（三处）

### 1. CONFIG —— main.py 的全部参数
脚本顶部 `CONFIG` 段，每个变量对应一个 main.py 参数，改值即可：

| 脚本变量 | 对应 main.py 参数 | 默认 |
|---|---|---|
| `PYTHON` | 跑 main.py 的解释器 | 启动本脚本的 python |
| `ADB_PATH` | `--adb_path` | adb 全路径 |
| `API_KEY` / `BASE_URL` / `MODEL` | `--api_key` / `--base_url` / `--model` | 主感知模型 |
| `SUMMARY_API_KEY` / `_BASE_URL` / `_MODEL` | `--summary_*` | 留空则回退主模型 |
| `COOR_TYPE` | `--coor_type` | `qwen-vl` |
| `OUTPUT_LANG` | `--output_lang` | `zh` |
| `PERCEPTION_MODE` | `--perception_mode` | `vllm`（`som`=调试） |
| `NOTETAKER` | `--notetaker` | `False` |
| `PRINT_DEVICE_CMD` | `--print_device_cmd` | `None`（按默认） |
| `PLANNER_TRICKS` / `PLANNER_TRICKS_TOPK` | `--planner_tricks*` | `off` / `0` |
| `REFLECTOR_TREE_CHECK` | `--reflector_tree_check` | `off` |
| `MAX_STEP_DEFAULT` | `--max_step` 全局默认 | `20` |
| `OUT_BASE` | `--run_dir_prefix` 的根目录 | `output/baseline` |

### 2. APPS —— 每个 app 跑哪个文件、几步、跑哪些场景
```python
APPS = {
    "哔哩哔哩": {"file": "哔哩哔哩_TestJson.json", "max_step": 20},
    "Chrono":   {"file": "Chrono_TestJson.json",   "max_step": 15},
}
```
- `max_step`：覆盖该 app 的步数（不写则用 `MAX_STEP_DEFAULT`）。
- 只跑部分场景（可选键）：
  - `"scenario_id": "S_xxx"` —— 只跑单个
  - `"start_id": "S_aaa", "end_id": "S_bbb"` —— 连续区间（含两端）
  - 都不写 = 跑该文件全部场景

  例：哔哩哔哩只跑前 3 个试水
  ```python
  "哔哩哔哩": {"file": "哔哩哔哩_TestJson.json", "max_step": 20,
              "start_id": "S_首页番剧动画栏目正常展示推荐列表_001",
              "end_id":   "S_点击单集进入播放器并加载正片_003"},
  ```

### 3. ASSIGNMENTS —— 哪台手机跑哪些 app
```python
ASSIGNMENTS = {
    "FJH5T18830019181": ["哔哩哔哩", "Chrono"],   # 这台顺序跑两个
    # "另一台序列号":     ["淘宝"],                # 多台会并行
}
```
- 不知道序列号：把这里清空（或保留「设备序列号N」占位），运行脚本会打印 adb 探测到的在线序列号，再回填。

---

## 输出
- `output/baseline/<app名>/`  每个 app 一个目录，内含各用例 run 目录（截图/步骤/报告）。
- `output/baseline/<app名>/batch_stdout.log`  该 app 整批的合并日志。
- 改 `OUT_BASE` 可换输出根目录。
