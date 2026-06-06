import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.actions import ANSWER
from core.agents.executor_agent import INPUT_KNOW, ExecutorAgent
from core.agents.path_summarizer_agent import PathSummarizerAgent
from core.agents.planner_agent import PlannerAgent
from core.agents.recorder_agent import RecorderAgent
from core.agents.reflector_agent import ReflectorAgent
from core.chains.execution_chain import ExecutionChain
from core.chains.planning_chain import PlanningChain
from core.chains.reflection_chain import ReflectionChain
from core.state.state_manager import StateManager
from infrastructure.device.device_controller import DeviceController
from infrastructure.llm.llm_provider import LLMProvider
from infrastructure.storage.log_service import LogService
from infrastructure.storage.report_service import ReportService
from services.action_service import ActionService
from services.screenshot_service import ScreenshotService


NO_COMPLETED_SUBGOAL = {
    "",
    "No completed subgoal.",
    "No completed subgoal",
    "鏃犲凡瀹屾垚瀛愮洰鏍囥€?",
    "鏃犲凡瀹屾垚瀛愮洰鏍?",
}


def _strip_answer_step(s: str) -> str:
    patterns = [
        r"\s*\d+\.\s*perform the `answer` action\.?",
        r"\s*\d+\.\s*perform the answer action\.?",
        r"\s*perform the `answer` action\.?",
        r"\s*perform the answer action\.?",
        r"\s*\d+\.\s*鎵ц `answer` 鍔ㄤ綔\.?",
        r"\s*\d+\.\s*鎵ц answer 鍔ㄤ綔\.?",
        r"\s*鎵ц `answer` 鍔ㄤ綔\.?",
        r"\s*鎵ц answer 鍔ㄤ綔\.?",
    ]
    for pattern in patterns:
        s = re.compile(pattern, re.IGNORECASE).sub(" ", s or "")
    return " ".join(s.split())


class TaskOrchestrator:
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
        perception_mode: str = "vllm",
        enable_tree_stagnation_check: bool = False,
        tree_similarity_threshold: float = 0.9,
    ):
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
        self.perception_mode = perception_mode

        self.planner_agent = PlannerAgent(llm_provider, state_manager)
        self.executor_agent = ExecutorAgent(llm_provider, state_manager)
        self.reflector_agent = ReflectorAgent(llm_provider, state_manager)
        self.recorder_agent = RecorderAgent(llm_provider, state_manager) if enable_notetaker else None
        self.path_summarizer_agent = PathSummarizerAgent(self.summary_llm_provider, state_manager)

        self.planning_chain = PlanningChain(self.planner_agent, state_manager)
        self.execution_chain = ExecutionChain(
            self.executor_agent,
            state_manager,
            action_service,
            screenshot_service,
            perception_mode,
        )
        self.reflection_chain = ReflectionChain(
            self.reflector_agent,
            state_manager,
            self.path_summarizer_agent,
            self.recorder_agent,
            enable_tree_stagnation_check=enable_tree_stagnation_check,
            tree_similarity_threshold=tree_similarity_threshold,
        )

        self.script_data = {"total_plan": "", "subgoals": []}
        self.infopool_data = {
            "plans": [],
            "completed_subgoals": [],
            "completed_subgoals_summary": [],
            "progress": [],
            "total_plan": "",
        }
        self.execution_history: List[str] = []
        self._last_command_str = None
        self._last_som_mark = None
        self.token_usage_by_role: Dict[str, Dict[str, int]] = {}

    def run(self, instruction: str, max_step: int = 25) -> str:
        self.state_manager.set_instruction(instruction)
        self.state_manager.set_additional_knowledge(executor=INPUT_KNOW)
        self.state_manager.set_perception_mode(self.perception_mode)

        start_time = datetime.now()
        local_image_dir = None
        local_image_dir2 = None

        for step in range(max_step):
            planning_result = None
            self.state_manager.reset_current_step_completed_subgoal()

            local_image_dir = self.screenshot_service.take_screenshot() if step == 0 else local_image_dir2
            if not local_image_dir:
                self._save_final_results(start_time, instruction, step_limit=1.0)
                self.device_controller.home()
                return self.log_service.log_dir

            if not self.screenshot_service.get_image_size(local_image_dir):
                continue

            self.state_manager.set_error_flag_plan(self.state_manager.check_error_threshold())

            skip_planner = False
            if not self.state_manager.get_error_flag_plan():
                last_action = self.state_manager.get_last_action()
                if last_action and last_action.get("action") == "invalid":
                    skip_planner = True

            if not skip_planner:
                print("\n ---INFO-Planner Agent---\n")
                planning_result = self.planning_chain.run(local_image_dir, skip_if_invalid=False)
                self._accumulate_tokens("planner", planning_result.get("_raw_response"))
                self.log_service.save_step_message(
                    step + 1,
                    "planner",
                    None,
                    planning_result.get("thought", "") + "\n" + planning_result.get("plan", ""),
                )
                self.log_service.append_chat_log("planner", planning_result.get("plan", ""), step + 1)
                print("New completed subgoal (from Planner): " + planning_result.get("completed_subgoal", ""))
                print("Planning thought: " + planning_result.get("thought", ""))
                print("Plan: " + planning_result.get("plan", ""), "\n")
                self._last_command_str = None

            plan = self.state_manager.get_plan()
            if "Finished" in plan.strip() and len(plan.strip()) < 15:
                print("Instruction finished, saving task result...")
                self._update_script_data(step, self._last_command_str, self._last_som_mark)
                self._persist_finish_thought(planning_result)
                self._update_infopool_data()
                self._save_final_results(start_time, instruction, step_limit=0.0)
                break

            current_step_text = self._extract_first_step(plan)

            print("\n ---INFO-Operator Agent---\n")
            execution_result = self.execution_chain.run(
                local_image_dir,
                self.coor_type,
                is_first_step=(step == 0),
            )
            self._accumulate_tokens("operator", execution_result.get("_raw_response"))

            action_object = execution_result.get("action_object")
            if not action_object:
                continue

            operator_response = f"""### Thought ###
{execution_result.get('thought', '')}

### Action ###
{json.dumps(action_object, ensure_ascii=False)}

### Description ###
{execution_result.get('description', '')}"""
            self.log_service.save_step_message(step + 1, "operator", None, operator_response)
            self.log_service.append_chat_log("operator", operator_response, step + 1)

            print("Thought: " + execution_result.get("thought", ""))
            print("Action: " + json.dumps(action_object, ensure_ascii=False))
            print("Action description: " + execution_result.get("description", ""))

            is_answer = action_object.get("action") == ANSWER
            if is_answer:
                answer_content = action_object.get("text", "")
                print(f"Instruction finished, answer: {answer_content}")
                # execution_chain 已将该 answer 动作记录到历史（outcome=S），此处不再重复 append，
                # 仅同步 last_action 以保持状态一致。
                self.state_manager.set_last_action(action_object, execution_result.get("description", ""))

            local_image_dir2 = self.screenshot_service.take_screenshot()
            if not local_image_dir2:
                self._save_final_results(start_time, instruction, step_limit=1.0)
                self.device_controller.home()
                return self.log_service.log_dir

            if is_answer:
                # answer 通常不改变屏幕，跳过反思（反思对其无意义，且会再次 append 污染历史）。
                # 直接同步进度状态，交由下一轮 Planner 标记 Finished 收尾。
                state = self.state_manager.get_state()
                self.state_manager.set_progress_status(state.planning.completed_plan_summary)
                if current_step_text:
                    self.execution_history.append(f"{current_step_text} (Success)")
            else:
                print("\n---INFO-ActionReflector Agent---\n")
                reflection_result = self.reflection_chain.run(
                    local_image_dir,
                    local_image_dir2,
                    step,
                    self.enable_notetaker,
                )
                self._accumulate_tokens("reflector", reflection_result.get("_reflector_raw_response"))
                self._accumulate_tokens("path_summarizer", reflection_result.get("_path_summarizer_raw_response"))
                self._accumulate_tokens("recorder", reflection_result.get("_recorder_raw_response"))

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
                    },
                )
                action_outcome = reflection_result.get("action_outcome", "")
                self.log_service.append_chat_log("action_reflector", action_outcome, step + 1)
                print("Action reflection outcome: " + action_outcome)
                print("Action reflection error description: " + reflection_result.get("error_description", ""))
                print("Action reflection progress status: " + self.state_manager.get_progress_status(), "\n")

                if current_step_text:
                    status = "Success" if action_outcome == "S" else "Fail"
                    self.execution_history.append(f"{current_step_text} ({status})")

            self.state_manager.set_prev_action_images(local_image_dir, local_image_dir2)
            self._last_command_str = execution_result.get("command_str")
            self._last_som_mark = execution_result.get("som_mark")
            self._update_script_data(step, self._last_command_str, self._last_som_mark)
            self._update_infopool_data()

        if not os.path.exists(os.path.join(self.log_service.log_dir, "task_results.json")):
            self._save_final_results(start_time, instruction, step_limit=1.0)

        self._append_last_subgoal_if_needed()
        self._save_script_and_infopool()
        self.device_controller.home()
        return self.log_service.log_dir

    def _persist_finish_thought(self, planning_result: Optional[Dict[str, Any]]) -> None:
        thought = (planning_result or {}).get("thought") or ""
        thought = str(thought).strip()
        if not thought:
            return
        try:
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

    def _save_final_results(self, start_time: datetime, instruction: str, step_limit: float) -> None:
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        start_formatted = start_time.strftime("%Y-%m-%d %H:%M:%S.%f")

        test_status_report = ""
        task_result_path = os.path.join(self.log_service.log_dir, "task_results.json")
        if os.path.exists(task_result_path):
            from infrastructure.storage.file_service import FileService

            data = FileService.read_json(task_result_path)
            if data:
                test_status_report = data.get("test_status_report", data.get("status_reason", ""))

        limit_hit = bool(step_limit and float(step_limit) != 0.0)
        task_status = "Not Completed" if limit_hit else "Completed"
        if limit_hit:
            test_status_report = test_status_report or "Reached maximum execution limit"
        else:
            test_status_report = test_status_report or "Finished within step limit"

        # 记录预期结果（测试预言），便于人复核"预期 vs 最终状态报告"
        try:
            expected_result = self.state_manager.get_expected_result()
            if expected_result:
                from infrastructure.storage.file_service import FileService

                existing = FileService.read_json(task_result_path) or {}
                if not isinstance(existing, dict):
                    existing = {}
                existing["expected_result"] = expected_result
                FileService.write_json(task_result_path, existing, ensure_ascii=False, indent=4)
        except Exception:
            pass

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
            execution_steps=self._count_exploration_steps(),
        )

    def _count_exploration_steps(self) -> int:
        steps_dir = os.path.join(self.log_service.log_dir, "Steps")
        if not os.path.isdir(steps_dir):
            return 0
        return sum(1 for d in os.listdir(steps_dir) if d.startswith("step_"))

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
                "total_tokens": total_tokens,
            }

        usage_md = getattr(raw_response, "usage_metadata", None)
        if isinstance(usage_md, dict):
            prompt_tokens = int(usage_md.get("input_tokens") or usage_md.get("prompt_tokens") or 0)
            completion_tokens = int(usage_md.get("output_tokens") or usage_md.get("completion_tokens") or 0)
            total_tokens = int(usage_md.get("total_tokens") or (prompt_tokens + completion_tokens))
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
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
                    "total_tokens": total_tokens,
                }
        return None

    def _accumulate_tokens(self, role: str, raw_response: Any) -> None:
        usage = self._extract_token_usage(raw_response)
        if not usage:
            return
        current = self.token_usage_by_role.get(role) or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        current["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
        current["completion_tokens"] += int(usage.get("completion_tokens", 0))
        current["total_tokens"] += int(usage.get("total_tokens", 0))
        self.token_usage_by_role[role] = current

    def _extract_first_step(self, plan: str) -> str:
        if not plan:
            return ""
        if "Finished" in plan and len(plan.strip()) < 15:
            return ""
        match = re.search(r"^\s*\d+\.\s*(.+?)(?=\n\d+\.|\n|$)", plan.strip(), re.DOTALL)
        if match:
            return match.group(1).strip()
        lines = plan.strip().split("\n")
        if lines:
            return re.sub(r"^\d+\.\s*", "", lines[0].strip()).strip()
        return ""

    def _combined_plan(self) -> str:
        state = self.state_manager.get_state()
        combined_plan = state.planning.plan
        if state.planning.completed_plan not in NO_COMPLETED_SUBGOAL:
            combined_plan = state.planning.completed_plan + "\n" + state.planning.plan
        return _strip_answer_step(combined_plan)

    def _update_script_data(self, step: int, command_str: Optional[str], som_mark: Optional[str] = None) -> None:
        self.script_data["total_plan"] = self._combined_plan()
        current_subgoal = self.state_manager.get_current_subgoal()
        if current_subgoal and command_str:
            image_before, image_after = self.state_manager.get_prev_action_images()
            info_dict = {
                "opter": command_str,
                "picture": [{"last": image_before or "", "next": image_after or ""}],
            }
            if self.perception_mode == "som":
                info_dict["mode"] = "som"
                if som_mark:
                    info_dict["mark"] = som_mark
            self.script_data["subgoals"].append({"subgoal": current_subgoal, "info": info_dict})

    def _update_infopool_data(self) -> None:
        state = self.state_manager.get_state()
        self.infopool_data["plans"].append(state.planning.plan)
        self.infopool_data["total_plan"] = self._combined_plan()
        self.infopool_data["progress"].append(state.reflection.progress_status)
        if state.planning.completed_plan and state.planning.completed_plan not in NO_COMPLETED_SUBGOAL:
            self.infopool_data["completed_subgoals"].append(state.planning.completed_plan)
        if state.planning.completed_plan_summary and state.planning.completed_plan_summary not in NO_COMPLETED_SUBGOAL:
            self.infopool_data["completed_subgoals_summary"].append(state.planning.completed_plan_summary)

    def _append_last_subgoal_if_needed(self) -> None:
        current_subgoal = self.state_manager.get_state().planning.current_subgoal
        if not current_subgoal or not self._last_command_str:
            return
        image_before, image_after = self.state_manager.get_prev_action_images()
        info_dict = {
            "opter": self._last_command_str,
            "picture": [{"last": image_before or "", "next": image_after or ""}],
        }
        if self.perception_mode == "som":
            info_dict["mode"] = "som"
            if self._last_som_mark:
                info_dict["mark"] = self._last_som_mark
        self.script_data["subgoals"].append({"subgoal": current_subgoal, "info": info_dict})

    def _save_script_and_infopool(self) -> None:
        self.report_service.save_script_data(
            self.log_service.log_dir,
            self.script_data["total_plan"],
            self.script_data["subgoals"],
        )
        self.report_service.save_infopool_data(
            self.log_service.log_dir,
            self.infopool_data["plans"],
            self.infopool_data["completed_subgoals"],
            self.infopool_data["completed_subgoals_summary"],
            self.infopool_data["progress"],
            self.infopool_data["total_plan"],
        )
