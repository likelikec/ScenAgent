from typing import Any, Dict, Optional

from core.agents.path_summarizer_agent import PathSummarizerAgent
from core.agents.recorder_agent import RecorderAgent
from core.agents.reflector_agent import ReflectorAgent
from core.state.state_manager import StateManager


class ReflectionChain:
    def __init__(
        self,
        reflector_agent: ReflectorAgent,
        state_manager: StateManager,
        path_summarizer_agent: Optional[PathSummarizerAgent] = None,
        recorder_agent: Optional[RecorderAgent] = None,
        enable_tree_stagnation_check: bool = False,
        tree_similarity_threshold: float = 0.9,
    ):
        self.reflector_agent = reflector_agent
        self.state_manager = state_manager
        self.path_summarizer_agent = path_summarizer_agent
        self.recorder_agent = recorder_agent
        self.enable_tree_stagnation_check = bool(enable_tree_stagnation_check)
        self.tree_similarity_threshold = float(tree_similarity_threshold or 0.0)
        self._tree_checker = None

    def run(
        self,
        before_screenshot: Optional[str] = None,
        after_screenshot: Optional[str] = None,
        step: int = 0,
        enable_notetaker: bool = False,
    ) -> Dict[str, Any]:
        images = []
        if before_screenshot:
            images.append(before_screenshot)
        if after_screenshot:
            images.append(after_screenshot)

        result = self.reflector_agent.run(images)
        outcome = result.get("outcome", "")
        error_description = result.get("error_description", "")

        if "S" in outcome:
            action_outcome = "S"
        elif "B" in outcome:
            action_outcome = "B"
        elif "C" in outcome:
            action_outcome = "C"
        else:
            raise ValueError(f"Invalid outcome: {outcome}")

        llm_outcome = action_outcome
        tree_similarity = None
        tree_confirmed = None
        tree_before_xml = None
        tree_after_xml = None
        final_outcome = action_outcome
        if action_outcome == "C" and self.enable_tree_stagnation_check:
            tree_similarity, tree_confirmed, tree_before_xml, tree_after_xml = self._confirm_tree_stagnation(
                before_screenshot,
                after_screenshot,
            )
            if tree_confirmed is True:
                final_outcome = "N"
            elif tree_confirmed is False:
                final_outcome = "S"

        state = self.state_manager.get_state()
        self.state_manager.set_progress_status(state.planning.completed_plan_summary)
        self.state_manager.append_action(
            state.execution.last_action,
            state.execution.last_summary,
            final_outcome,
            error_description,
        )

        path_summarizer_raw_response = None
        if (step + 1) % 5 == 0 and final_outcome == "S" and self.path_summarizer_agent:
            path_summarizer_raw_response = self._run_path_summarizer()

        recorder_raw_response = None
        if final_outcome == "S" and enable_notetaker and self.recorder_agent:
            recorder_raw_response = self._run_recorder(after_screenshot)

        return {
            "outcome": outcome,
            "error_description": error_description,
            "action_outcome": final_outcome,
            "llm_outcome": llm_outcome,
            "tree_similarity": tree_similarity,
            "tree_confirmed": tree_confirmed,
            "tree_before_xml": tree_before_xml,
            "tree_after_xml": tree_after_xml,
            "final_outcome": final_outcome,
            "_reflector_raw_response": result.get("_raw_response"),
            "_path_summarizer_raw_response": path_summarizer_raw_response,
            "_recorder_raw_response": recorder_raw_response,
        }

    def _confirm_tree_stagnation(self, before_screenshot: Optional[str], after_screenshot: Optional[str]):
        if self._tree_checker is None:
            from core.chains.tree_stagnation_checker import UiTreeStagnationChecker

            self._tree_checker = UiTreeStagnationChecker(self.tree_similarity_threshold)
        return self._tree_checker.confirm(before_screenshot, after_screenshot)

    def _run_path_summarizer(self) -> Any:
        if not self.path_summarizer_agent:
            return None
        print("Running Path Summarizer...")
        result = self.path_summarizer_agent.run([])
        summary = result.get("summary", "")
        if summary:
            self.state_manager.set_completed_plan_summary(summary)
            print(f"Path summary updated: {summary}")
        return result.get("_raw_response")

    def _run_recorder(self, screenshot_path: str) -> Any:
        if not self.recorder_agent or not screenshot_path:
            return None
        print("Running Recorder...")
        result = self.recorder_agent.run([screenshot_path])
        important_notes = result.get("important_notes", "")
        if important_notes:
            self.state_manager.set_important_notes(important_notes)
            print(f"Important notes updated: {important_notes}")
        return result.get("_raw_response")
