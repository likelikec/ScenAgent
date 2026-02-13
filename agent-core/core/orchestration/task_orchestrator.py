
import os
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from PIL import Image

from core.state.state_manager import StateManager
from core.chains.planning_chain import PlanningChain
from core.chains.execution_chain import ExecutionChain
from core.chains.reflection_chain import ReflectionChain
from core.agents.planner_agent import PlannerAgent
from core.agents.executor_agent import ExecutorAgent
from core.agents.reflector_agent import ReflectorAgent
from core.agents.recorder_agent import RecorderAgent
from core.agents.task_judge_agent import TaskJudgeAgent
from core.agents.path_summarizer_agent import PathSummarizerAgent
from infrastructure.llm.llm_provider import LLMProvider
from infrastructure.device.device_controller import DeviceController
from infrastructure.storage.log_service import LogService
from infrastructure.storage.report_service import ReportService
from services.screenshot_service import ScreenshotService
from services.action_service import ActionService
from services.coordinate_service import CoordinateService
from core.actions import ANSWER
from core.agents.executor_agent import INPUT_KNOW


def _strip_answer_step(s: str) -> str:
    """移除计划中的answer步骤（用于显示）"""
    patterns = [
        r"\s*\d+\.\s*perform the `answer` action\.?",
        r"\s*\d+\.\s*perform the answer action\.?",
        r"\s*perform the `answer` action\.?",
        r"\s*perform the answer action\.?",
        r"\s*\d+\.\s*执行 `answer` 动作\.?",
        r"\s*\d+\.\s*执行 answer 动作\.?",
        r"\s*执行 `answer` 动作\.?",
        r"\s*执行 answer 动作\.?",
    ]
    for p in patterns:
        s = re.compile(p, re.IGNORECASE).sub(" ", s)
    return " ".join(s.split())


class TaskOrchestrator:
    """任务编排器类"""
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        summary_llm_provider: Optional[LLMProvider],
        device_controller: DeviceController,
        log_service: LogService,
        report_service: ReportService,
        screenshot_service: ScreenshotService,
        action_service: ActionService,
        state_manager: StateManager,
        coor_type: str = "abs",
        enable_notetaker: bool = False,
        enable_task_judge: bool = True,
        perception_mode: str = "vllm",
        enable_tree_stagnation_check: bool = False,
        tree_similarity_threshold: float = 0.9,
    ):
        """初始化任务编排器
        
        Args:
            llm_provider: 主LLM提供者
            summary_llm_provider: 摘要LLM提供者（可选）
            device_controller: 设备控制器
            log_service: 日志服务
            report_service: 报告服务
            screenshot_service: 截图服务
            action_service: 动作执行服务
            state_manager: 状态管理器
            coor_type: 坐标类型
            enable_notetaker: 是否启用Notetaker
            perception_mode: 感知模式 ("vllm" 或 "som")
        """
        self.llm_provider = llm_provider
        self.summary_llm_provider = summary_llm_provider or llm_provider
        self.device_controller = device_controller
        self.log_service = log_service
        self.report_service = report_service
        self.screenshot_service = screenshot_service
        self.action_service = action_service
        self.state_manager = state_manager
        self.coor_type = coor_type
        self.enable_notetaker = enable_notetaker
        self.enable_task_judge = bool(enable_task_judge)
        self.perception_mode = perception_mode
        self.enable_tree_stagnation_check = bool(enable_tree_stagnation_check)
        self.tree_similarity_threshold = float(tree_similarity_threshold or 0.0)
        
        # 创建Agents
        self.planner_agent = PlannerAgent(llm_provider, state_manager)
        self.executor_agent = ExecutorAgent(llm_provider, state_manager)
        self.reflector_agent = ReflectorAgent(llm_provider, state_manager)
        self.recorder_agent = RecorderAgent(llm_provider, state_manager) if enable_notetaker else None
        self.task_judge_agent = TaskJudgeAgent(llm_provider, state_manager)
        self.path_summarizer_agent = PathSummarizerAgent(self.summary_llm_provider, state_manager)
        
        # 创建Chains
        self.planning_chain = PlanningChain(self.planner_agent, state_manager)
        self.execution_chain = ExecutionChain(
            self.executor_agent,
            state_manager,
            action_service,
            screenshot_service,
            perception_mode
        )
        self.reflection_chain = ReflectionChain(
            self.reflector_agent,
            state_manager,
            self.path_summarizer_agent,
            self.recorder_agent,
            enable_tree_stagnation_check=self.enable_tree_stagnation_check,
            tree_similarity_threshold=self.tree_similarity_threshold,
        )
        
        # 初始化数据
        self.script_data = {"total_plan": "", "subgoals": []}
        self.infopool_data = {
            "plans": [],
            "completed_subgoals": [],
            "completed_subgoals_summary": [],
            "progress": [],
            "total_plan": ""
        }
        self.execution_history: List[str] = []
        self._last_command_str = None
        self._last_som_mark = None
        self.token_usage_by_role: Dict[str, Dict[str, int]] = {}
    
    def run(
        self,
        instruction: str,
        max_step: int = 25
    ) -> str:
        """运行任务
        
        Args:
            instruction: 任务指令
            max_step: 最大步数
            
        Returns:
            运行目录路径
        """
        # 初始化状态
        self.state_manager.set_instruction(instruction)
        self.state_manager.set_additional_knowledge(
            executor=INPUT_KNOW
        )
        self.state_manager.set_perception_mode(self.perception_mode)
        
        start_time = datetime.now()
        local_image_dir = None
        local_image_dir2 = None
        
        for step in range(max_step):
            planning_result = None
            # 重置当前步骤的新完成子目标
            self.state_manager.reset_current_step_completed_subgoal()
            
            # 获取截图
            if step == 0:
                local_image_dir = self.screenshot_service.take_screenshot()
            else:
                local_image_dir = local_image_dir2
            
            if not local_image_dir:
                # 截图失败，保存结果并退出
                self._save_final_results(start_time, instruction, step_limit=1.0)
                self.device_controller.home()
                return self.log_service.log_dir
            
            # 获取屏幕尺寸
            size = self.screenshot_service.get_image_size(local_image_dir)
            if not size:
                continue
            width, height = size
            
            # 检查错误阈值
            self.state_manager.set_error_flag_plan(
                self.state_manager.check_error_threshold()
            )
            
            # 规划阶段
            skip_planner = False
            if not self.state_manager.get_error_flag_plan():
                last_action = self.state_manager.get_last_action()
                if last_action and last_action.get('action') == 'invalid':
                    skip_planner = True
            
            if not skip_planner:
                print("\n ---INFO-Planner Agent---\n")
                planning_result = self.planning_chain.run(
                    local_image_dir,
                    skip_if_invalid=False
                )
                self._accumulate_tokens("planner", planning_result.get("_raw_response"))
                
                # 保存规划结果
                self.log_service.save_step_message(
                    step + 1,
                    "planner",
                    None,  # messages将在后续版本中保存
                    planning_result.get('thought', '') + "\n" + planning_result.get('plan', '')
                )
                self.log_service.append_chat_log("planner", planning_result.get('plan', ''), step + 1)
                
                print('New completed subgoal (from Planner): ' + planning_result.get('completed_subgoal', ''))
                print('Completed subgoal summary (used by Planner): ' + (
                    self.state_manager.get_state().planning.completed_plan_summary
                    if self.state_manager.get_state().planning.completed_plan_summary not in ["无已完成子目标。", "No completed subgoal.", "无已完成子目标", "No completed subgoal"]
                    else "No completed subgoal summary."
                ))
                print('Planning thought: ' + planning_result.get('thought', ''))
                print('Plan: ' + planning_result.get('plan', ''), "\n")

                # self._update_script_data(step, self._last_command_str)
                self._last_command_str = None
            
            # 检查是否完成
            plan = self.state_manager.get_plan()
            if "Finished" in plan.strip() and len(plan.strip()) < 15:
                print("Instruction finished, evaluating task result...")
                self._update_script_data(step, self._last_command_str, self._last_som_mark)
                try:
                    thought = (planning_result or {}).get("thought") or ""
                    thought = str(thought).strip()
                    if thought:
                        from infrastructure.storage.file_service import FileService

                        task_result_path = os.path.join(self.log_service.log_dir, "task_results.json")
                        existing = FileService.read_json(task_result_path) or {}
                        if not isinstance(existing, dict):
                            existing = {}
                        existing["test_status_report"] = thought
                        existing.pop("status_reason", None)
                        existing.pop("status_reason_zh", None)
                        FileService.write_json(task_result_path, existing, ensure_ascii=False, indent=4)
                except Exception:
                    pass
                if self.enable_task_judge:
                    self._run_task_judge(local_image_dir, step + 1)
                self._update_infopool_data()
                self._save_final_results(start_time, instruction, step_limit=0.0)
                break
            
            # 获取当前要执行的步骤文本
            current_step_text = self._extract_first_step(plan)
            
            # 执行阶段
            print("\n ---INFO-Operator Agent---\n")
            execution_result = self.execution_chain.run(
                local_image_dir,
                self.coor_type,
                is_first_step=(step == 0)
            )
            self._accumulate_tokens("operator", execution_result.get("_raw_response"))
            
            action_object = execution_result.get('action_object')
            if not action_object:
                continue
            
            # 保存执行结果
            operator_response = f'''### Thought ###
{execution_result.get('thought', '')}

### Action ###
{json.dumps(action_object, ensure_ascii=False)}

### Description ###
{execution_result.get('description', '')}'''
            self.log_service.save_step_message(
                step + 1,
                "operator",
                None,
                operator_response
            )
            self.log_service.append_chat_log("operator", operator_response, step + 1)
            
            print('Thought: ' + execution_result.get('thought', ''))
            print('Action: ' + json.dumps(action_object, ensure_ascii=False))
            print('Action description: ' + execution_result.get('description', ''))
            
            # 处理answer动作
            if action_object.get('action') == ANSWER:
                answer_content = action_object.get('text', '')
                print(f"Instruction finished, answer: {answer_content}")
                
                # 将answer操作加入历史
                self.state_manager.set_last_action(action_object, execution_result.get('description', ''))
                self.state_manager.append_action(
                    action_object,
                    execution_result.get('description', ''),
                    "S",
                    "None"
                )
                # 修改：Answer后不直接退出，而是继续流程（拍照->反思->下一轮规划）
                # 为了兼容反思Agent，我们需要“假装”拍了一张新照片（或者直接复用旧照片）
                # 这里我们选择继续执行后续的 take_screenshot 逻辑，虽然屏幕可能没变
            
            # 获取操作后的截图
            local_image_dir2 = self.screenshot_service.take_screenshot()
            if not local_image_dir2:
                self._save_final_results(start_time, instruction, step_limit=1.0)
                self.device_controller.home()
                return self.log_service.log_dir
            
            # 反思阶段
            print("\n---INFO-ActionReflector Agent---\n")
            reflection_result = self.reflection_chain.run(
                local_image_dir,
                local_image_dir2,
                step,
                self.enable_notetaker
            )
            self._accumulate_tokens("reflector", reflection_result.get("_reflector_raw_response"))
            self._accumulate_tokens("path_summarizer", reflection_result.get("_path_summarizer_raw_response"))
            self._accumulate_tokens("recorder", reflection_result.get("_recorder_raw_response"))
            
            # 保存反思结果
            tree_similarity = reflection_result.get("tree_similarity")
            tree_similarity_text = f"{tree_similarity:.4f}" if isinstance(tree_similarity, (int, float)) else "None"
            self.log_service.save_step_message(
                step + 1,
                "reflector",
                None,
                "LLM Outcome: "
                + str(reflection_result.get("llm_outcome", ""))
                + "\nTree Similarity: "
                + tree_similarity_text
                + "\nFinal Outcome: "
                + str(reflection_result.get("final_outcome", ""))
                + "\nError Description: "
                + str(reflection_result.get("error_description", "")),
                extra={
                    "llm_outcome": reflection_result.get("llm_outcome"),
                    "tree_similarity": reflection_result.get("tree_similarity"),
                    "tree_confirmed": reflection_result.get("tree_confirmed"),
                    "tree_before_xml": reflection_result.get("tree_before_xml"),
                    "tree_after_xml": reflection_result.get("tree_after_xml"),
                    "final_outcome": reflection_result.get("final_outcome"),
                }
            )
            action_outcome = reflection_result.get('action_outcome', '')
            self.log_service.append_chat_log("action_reflector", action_outcome, step + 1)
            print('Action reflection outcome: ' + action_outcome)
            print('Action reflection error description: ' + reflection_result.get('error_description', ''))
            print('Action reflection progress status: ' + self.state_manager.get_progress_status(), "\n")
            
            # 更新执行历史
            if current_step_text:
                status = "Success" if action_outcome == 'S' else "Fail"
                self.execution_history.append(f"{current_step_text} ({status})")
            
            self.state_manager.set_prev_action_images(local_image_dir, local_image_dir2)
            self._last_command_str = execution_result.get('command_str')
            self._last_som_mark = execution_result.get('som_mark')
            
            # 更新数据
            self._update_script_data(step, self._last_command_str, self._last_som_mark)
            self._update_infopool_data()
        
        # 检查是否达到最大步数
        if not os.path.exists(os.path.join(self.log_service.log_dir, "task_results.json")):
            self._save_final_results(start_time, instruction, step_limit=1.0)
        
        # 补录最后一步的subgoal
        # 如果当前循环结束时，还有一个current_subgoal正在进行中（即Operator执行了动作但Planner还没来得及确认完成）
        # 我们通常认为这个动作是为了完成当前的current_subgoal
        # 注意：这里我们使用 state_manager.get_current_subgoal() 而不是 completed_subgoal
        state = self.state_manager.get_state()
        current_subgoal = state.planning.current_subgoal
        if current_subgoal and self._last_command_str:
             # 获取最后一次操作的截图
            image_before, image_after = self.state_manager.get_prev_action_images()
            if not image_before: image_before = ""
            if not image_after: image_after = ""
            
            # Build info dict with mode metadata
            info_dict = {
                "opter": self._last_command_str,
                "picture": [
                    {"last": image_before, "next": image_after}
                ]
            }
            
            # Add SoM metadata if applicable
            if self.perception_mode == "som":
                info_dict["mode"] = "som"
                if self._last_som_mark:
                    info_dict["mark"] = self._last_som_mark
            
            self.script_data["subgoals"].append({
                "subgoal": current_subgoal,
                "info": info_dict
            })

        # 保存最终数据
        self._save_script_and_infopool()
        self.device_controller.home()
        
        return self.log_service.log_dir
    
    def _run_task_judge(self, screenshot_path: str, step: int) -> None:
        """运行TaskJudge"""
        print("\n---INFO-Judger Agent---\n")
        result = self.task_judge_agent.run([screenshot_path])
        self._accumulate_tokens("task_judge", result.get("_raw_response"))
        
        # 调试：打印原始响应
        if not result.get('task_status') and not result.get('status_reason'):
             print(f"[DEBUG] Judger Raw Response: {result.get('_raw_response')}")

        # 保存TaskJudge结果
        content = f"Task Status: {result.get('task_status', '')}\nStatus Reason: {result.get('status_reason', '')}"
        if result.get("app_tricks"):
            try:
                content += "\nApp Tricks: " + json.dumps(result.get("app_tricks"), ensure_ascii=False)
            except Exception:
                pass
        self.log_service.save_step_message(
            step,
            "task_judge",
            None,
            content
        )
        self.log_service.append_chat_log("task_judge", content, step)
        
        print(f"任务状态: {result.get('task_status', '')}")
        print(f"状态原因: {result.get('status_reason', '')}\n")

        self._persist_app_tricks(result)

        try:
            from infrastructure.storage.file_service import FileService

            task_result_path = os.path.join(self.log_service.log_dir, "task_results.json")
            existing = FileService.read_json(task_result_path) or {}
            if not isinstance(existing, dict):
                existing = {}
            existing["task_judger"] = result.get("task_status", "") or ""
            existing["judger_reason"] = result.get("status_reason", "") or ""
            FileService.write_json(task_result_path, existing, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def _extract_target_app_name(self) -> str:
        s = (self.state_manager.get_state().task.additional_knowledge_planner or "").strip()
        if not s:
            return "Unknown"
        m = re.search(
            r"Target\s*app\s*:\s*(.+?)(?:\s*(?:\.|。)\s*Extra\s*:|\s*(?:\.|。)|$)",
            s,
            flags=re.IGNORECASE,
        )
        name = (m.group(1) if m else "").strip()
        return name or "Unknown"

    def _persist_app_tricks(self, task_judge_result: Dict[str, Any]) -> None:
        tricks = task_judge_result.get("app_tricks") or []
        if not isinstance(tricks, list) or len(tricks) == 0:
            return

        from infrastructure.storage.file_service import FileService

        app_name = self._extract_target_app_name()
        tricks_path = os.path.join(os.path.dirname(self.log_service.log_dir), "tricks.json")
        existing = FileService.read_json(tricks_path) or {}
        if not isinstance(existing, dict):
            existing = {}

        bucket = existing.get(app_name)
        if not isinstance(bucket, list):
            bucket = []

        seen = set()
        for it in bucket:
            if isinstance(it, dict):
                seen.add((str(it.get("type") or ""), str(it.get("title") or ""), str(it.get("content") or "")))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task_name = self.state_manager.get_task_name()
        instruction = self.state_manager.get_state().task.instruction
        task_label = task_name or instruction
        for it in tricks:
            if not isinstance(it, dict):
                continue
            trick_type = str(it.get("type") or "").strip()
            title = str(it.get("title") or "").strip()
            content = str(it.get("content") or "").strip()
            if not title and not content:
                continue
            key = (trick_type, title, content)
            if key in seen:
                continue
            seen.add(key)
            bucket.append(
                {
                    "type": trick_type,
                    "title": title,
                    "content": content,
                    "tags": it.get("tags") if isinstance(it.get("tags"), list) else [],
                    "evidence_steps": it.get("evidence_steps") if isinstance(it.get("evidence_steps"), list) else [],
                    "created_at": now,
                    "run_dir": self.log_service.log_dir,
                    "task_instruction": task_label,
                    "task_status": task_judge_result.get("task_status", ""),
                }
            )

        existing[app_name] = bucket
        FileService.write_json(tricks_path, existing, ensure_ascii=False, indent=2)
    
    def _save_final_results(
        self,
        start_time: datetime,
        instruction: str,
        step_limit: float
    ) -> None:
        """保存最终结果"""
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        start_formatted = start_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # 读取task_status（如果已保存）
        task_status = ""
        test_status_report = ""
        task_result_path = os.path.join(self.log_service.log_dir, "task_results.json")
        if os.path.exists(task_result_path):
            from infrastructure.storage.file_service import FileService
            data = FileService.read_json(task_result_path)
            if data:
                task_status = data.get("task_status", "")
                test_status_report = data.get("test_status_report", data.get("status_reason", ""))

        limit_hit = bool(step_limit and float(step_limit) != 0.0)
        task_status = "Not Completed" if limit_hit else "Completed"
        if limit_hit:
            test_status_report = test_status_report or "Reached maximum execution limit"
        else:
            test_status_report = test_status_report or "Finished within step limit"
        
        execution_steps = self._count_exploration_steps()
        token_usage = self.token_usage_by_role
        total_tokens = sum(v.get("total_tokens", 0) for v in (token_usage or {}).values())
        
        self.report_service.save_task_results(
            self.log_service.log_dir,
            instruction,
            start_formatted,
            formatted_time,
            step_limit,
            task_status,
            test_status_report,
            token_usage=token_usage,
            total_tokens=total_tokens,
            execution_steps=execution_steps
        )

    def _count_exploration_steps(self) -> int:
        steps_dir = os.path.join(self.log_service.log_dir, "Steps")
        if not os.path.isdir(steps_dir):
            return 0

        step_folders = []
        for d in os.listdir(steps_dir):
            if not d.startswith("step_"):
                continue
            try:
                n = int(d.split("_")[-1])
            except Exception:
                n = 0
            step_folders.append((n, d))

        step_folders.sort(key=lambda x: x[0])
        if not step_folders:
            return 0

        total = len(step_folders)
        last_step_dir = os.path.join(steps_dir, step_folders[-1][1])
        if (
            os.path.exists(os.path.join(last_step_dir, "task_judge.json"))
            or os.path.exists(os.path.join(last_step_dir, "task_judge.zh.json"))
        ):
            total -= 1

        return max(total, 0)

    def _extract_token_usage(self, raw_response: Any) -> Optional[Dict[str, int]]:
        if raw_response is None:
            return None
        
        usage_obj = getattr(raw_response, "usage", None)
        if usage_obj:
            if isinstance(usage_obj, dict):
                prompt_tokens = usage_obj.get("prompt_tokens") or usage_obj.get("input_tokens")
                completion_tokens = usage_obj.get("completion_tokens") or usage_obj.get("output_tokens")
                total_tokens = usage_obj.get("total_tokens")
            else:
                prompt_tokens = getattr(usage_obj, "prompt_tokens", None) or getattr(usage_obj, "input_tokens", None)
                completion_tokens = getattr(usage_obj, "completion_tokens", None) or getattr(usage_obj, "output_tokens", None)
                total_tokens = getattr(usage_obj, "total_tokens", None)
            
            prompt_tokens = int(prompt_tokens or 0)
            completion_tokens = int(completion_tokens or 0)
            total_tokens = int(total_tokens or (prompt_tokens + completion_tokens))
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        
        usage_md = getattr(raw_response, "usage_metadata", None)
        if isinstance(usage_md, dict):
            prompt_tokens = int(usage_md.get("input_tokens") or usage_md.get("prompt_tokens") or 0)
            completion_tokens = int(usage_md.get("output_tokens") or usage_md.get("completion_tokens") or 0)
            total_tokens = int(usage_md.get("total_tokens") or (prompt_tokens + completion_tokens))
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        
        resp_md = getattr(raw_response, "response_metadata", None)
        if isinstance(resp_md, dict):
            token_usage = resp_md.get("token_usage") or resp_md.get("usage")
            if isinstance(token_usage, dict):
                prompt_tokens = int(token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0)
                completion_tokens = int(token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0)
                total_tokens = int(token_usage.get("total_tokens") or (prompt_tokens + completion_tokens))
                return {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                }
        
        return None

    def _accumulate_tokens(self, role: str, raw_response: Any) -> None:
        usage = self._extract_token_usage(raw_response)
        if not usage:
            return
        current = self.token_usage_by_role.get(role) or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        current["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
        current["completion_tokens"] += int(usage.get("completion_tokens", 0))
        current["total_tokens"] += int(usage.get("total_tokens", 0))
        self.token_usage_by_role[role] = current
    
    def _extract_first_step(self, plan: str) -> str:
        """从计划中提取第一步的文本描述（移除编号）"""
        if not plan:
            return ""
        
        # 移除Finished
        if "Finished" in plan and len(plan.strip()) < 15:
            return ""
            
        # 使用正则提取带编号的步骤
        match = re.search(r'^\s*\d+\.\s*(.+?)(?=\n\d+\.|\n|$)', plan.strip(), re.DOTALL)
        if match:
            return match.group(1).strip()
            
        # 降级：提取第一行
        lines = plan.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            # 尝试移除开头的编号
            return re.sub(r'^\d+\.\s*', '', first_line).strip()
            
        return ""

    def _normalize_text(self, text: str) -> str:
        """标准化文本以进行比较"""
        # 移除标点符号和空白
        return re.sub(r'[\s\.\,，。、]+', '', text.lower())

    def _update_script_data(self, step: int, command_str: Optional[str], som_mark: Optional[str] = None) -> None:
        """更新script数据"""
        # 使用与infopool.json一致的逻辑：已完成计划 + 剩余计划
        state = self.state_manager.get_state()
        combined_plan = state.planning.plan
        if state.planning.completed_plan not in ["无已完成子目标。", "No completed subgoal.", "无已完成子目标", "No completed subgoal"]:
            combined_plan = state.planning.completed_plan + "\n" + state.planning.plan
        combined_plan = _strip_answer_step(combined_plan)
        
        self.script_data["total_plan"] = combined_plan
        
        # 修正逻辑：使用 current_subgoal 而非 completed_subgoal
        # 我们记录的是：当前这一步的动作(command_str)是为了完成哪个目标(current_subgoal)
        current_subgoal = self.state_manager.get_current_subgoal()
        
        # 只有当存在有效动作和当前目标时才记录
        if current_subgoal and command_str:
            image_before, image_after = self.state_manager.get_prev_action_images()
            if not image_before:
                image_before = ""
            if not image_after:
                image_after = ""
            
            # Build info dict with mode metadata
            info_dict = {
                "opter": command_str,
                "picture": [
                    {"last": image_before, "next": image_after}
                ]
            }
            
            # Add SoM metadata if applicable
            if self.perception_mode == "som":
                info_dict["mode"] = "som"
                if som_mark:
                    info_dict["mark"] = som_mark
            
            self.script_data["subgoals"].append({
                "subgoal": current_subgoal,
                "info": info_dict
            })
    
    def _update_infopool_data(self) -> None:
        """更新infopool数据"""
        state = self.state_manager.get_state()
        self.infopool_data["plans"].append(state.planning.plan)
        
        combined_plan = state.planning.plan
        if state.planning.completed_plan not in ["无已完成子目标。", "No completed subgoal.", "无已完成子目标", "No completed subgoal"]:
            combined_plan = state.planning.completed_plan + "\n" + state.planning.plan
        combined_plan = _strip_answer_step(combined_plan)
        self.infopool_data["total_plan"] = combined_plan
        
        self.infopool_data["progress"].append(state.reflection.progress_status)
        if state.planning.completed_plan and state.planning.completed_plan not in ["无已完成子目标。", "No completed subgoal.", "无已完成子目标", "No completed subgoal"]:
            self.infopool_data["completed_subgoals"].append(state.planning.completed_plan)
        if state.planning.completed_plan_summary and state.planning.completed_plan_summary not in ["无已完成子目标。", "No completed subgoal.", "无已完成子目标", "No completed subgoal"]:
            self.infopool_data["completed_subgoals_summary"].append(state.planning.completed_plan_summary)
    
    def _save_script_and_infopool(self) -> None:
        """保存script和infopool数据"""
        self.report_service.save_script_data(
            self.log_service.log_dir,
            self.script_data["total_plan"],
            self.script_data["subgoals"]
        )
        self.report_service.save_infopool_data(
            self.log_service.log_dir,
            self.infopool_data["plans"],
            self.infopool_data["completed_subgoals"],
            self.infopool_data["completed_subgoals_summary"],
            self.infopool_data["progress"],
            self.infopool_data["total_plan"]
        )

