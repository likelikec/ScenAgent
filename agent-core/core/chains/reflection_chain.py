"""反思Chain：连接ReflectorAgent和状态更新"""
import os
import re
from typing import Dict, Any, Optional, List, Tuple
from core.agents.reflector_agent import ReflectorAgent
from core.agents.path_summarizer_agent import PathSummarizerAgent
from core.agents.recorder_agent import RecorderAgent
from core.state.state_manager import StateManager
from infrastructure.llm.llm_provider import LLMProvider
try:
    import xmltodict
except ImportError:
    xmltodict = None


class _UiTreeStagnationChecker:
    def __init__(self, tree_similarity_threshold: float = 0.9):
        self.tree_similarity_threshold = float(tree_similarity_threshold or 0.0)

    def confirm(
        self,
        before_screenshot: Optional[str],
        after_screenshot: Optional[str],
    ) -> Tuple[Optional[float], Optional[bool], Optional[str], Optional[str]]:
        if not before_screenshot or not after_screenshot:
            return None, None, None, None
        if xmltodict is None:
            return None, None, None, None
        before_xml = self._resolve_xml_path(before_screenshot)
        after_xml = self._resolve_xml_path(after_screenshot)
        if not before_xml or not after_xml:
            return None, None, None, None
        before_tokens = self._extract_ui_tokens(before_xml)
        after_tokens = self._extract_ui_tokens(after_xml)
        if not before_tokens or not after_tokens:
            return None, None, before_xml, after_xml
        similarity = self._jaccard_similarity(before_tokens, after_tokens)
        if similarity is None:
            return None, None, before_xml, after_xml
        return similarity, similarity >= self.tree_similarity_threshold, before_xml, after_xml

    def _resolve_xml_path(self, screenshot_path: str) -> Optional[str]:
        if not screenshot_path:
            return None
        base_name = os.path.basename(screenshot_path)
        parent_dir = os.path.dirname(screenshot_path)
        if base_name.endswith("_marked.png") and os.path.basename(parent_dir) == "marked":
            origin_name = base_name.replace("_marked.png", ".png")
            xml_path = os.path.join(os.path.dirname(parent_dir), os.path.splitext(origin_name)[0] + ".xml")
        else:
            xml_path = os.path.splitext(screenshot_path)[0] + ".xml"
        if os.path.exists(xml_path):
            return xml_path
        return None

    def _extract_ui_tokens(self, xml_path: str) -> List[str]:
        try:
            with open(xml_path, "r", encoding="utf-8") as f:
                xml_content = f.read()
            parsed = xmltodict.parse(xml_content)
        except Exception:
            return []
        root = parsed.get("hierarchy") if isinstance(parsed, dict) else None
        nodes = root.get("node") if isinstance(root, dict) else None
        primary_package = self._infer_primary_package(nodes)
        tokens: List[str] = []
        self._collect_tokens_from_node(nodes, tokens, primary_package)
        return tokens

    def _collect_tokens_from_node(self, node: Any, tokens: List[str], primary_package: str) -> None:
        if isinstance(node, list):
            for child in node:
                self._collect_tokens_from_node(child, tokens, primary_package)
            return
        if not isinstance(node, dict):
            return
        attrs = node
        pkg = self._get_attr(attrs, "package")
        cls = self._get_attr(attrs, "class")
        res_id = self._get_attr(attrs, "resource-id")
        text = self._get_attr(attrs, "text")
        content_desc = self._get_attr(attrs, "content-desc")
        hint = self._get_attr(attrs, "hint")
        bounds = self._get_attr(attrs, "bounds")
        clickable = self._get_attr(attrs, "clickable")
        scrollable = self._get_attr(attrs, "scrollable")
        editable = self._get_attr(attrs, "editable")
        checkable = self._get_attr(attrs, "checkable")
        checked = self._get_attr(attrs, "checked")
        enabled = self._get_attr(attrs, "enabled")
        selected = self._get_attr(attrs, "selected")
        focused = self._get_attr(attrs, "focused")
        flags = ",".join(
            f for f, v in [
                ("clickable", clickable),
                ("scrollable", scrollable),
                ("editable", editable),
                ("checkable", checkable),
                ("checked", checked),
                ("enabled", enabled),
                ("selected", selected),
                ("focused", focused),
            ]
            if v == "true"
        )
        text = self._normalize_text(text)
        content_desc = self._normalize_text(content_desc)
        hint = self._normalize_text(hint)
        if not primary_package or not pkg or pkg == primary_package:
            token = "|".join([
                cls,
                res_id,
                text[:80] if text else "",
                content_desc[:80] if content_desc else "",
                hint[:80] if hint else "",
                bounds,
                flags
            ])
            tokens.append(token)
        children = node.get("node")
        if children is not None:
            self._collect_tokens_from_node(children, tokens, primary_package)

    def _infer_primary_package(self, node: Any) -> str:
        counts: Dict[str, int] = {}
        self._collect_package_counts(node, counts)
        if not counts:
            return ""
        return max(counts.items(), key=lambda it: it[1])[0]

    def _collect_package_counts(self, node: Any, counts: Dict[str, int]) -> None:
        if isinstance(node, list):
            for child in node:
                self._collect_package_counts(child, counts)
            return
        if not isinstance(node, dict):
            return
        pkg = self._get_attr(node, "package")
        if pkg:
            counts[pkg] = counts.get(pkg, 0) + 1
        children = node.get("node")
        if children is not None:
            self._collect_package_counts(children, counts)

    def _get_attr(self, node: Dict[str, Any], key: str) -> str:
        val = node.get(f"@{key}")
        if val is None:
            val = node.get(key)
        return "" if val is None else str(val)

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", str(text)).strip().lower()

    def _jaccard_similarity(self, tokens_a: List[str], tokens_b: List[str]) -> Optional[float]:
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        if not set_a and not set_b:
            return None
        union = set_a | set_b
        if not union:
            return None
        return len(set_a & set_b) / len(union)


class ReflectionChain:
    """反思Chain：负责反思阶段的处理"""
    
    def __init__(
        self,
        reflector_agent: ReflectorAgent,
        state_manager: StateManager,
        path_summarizer_agent: Optional[PathSummarizerAgent] = None,
        recorder_agent: Optional[RecorderAgent] = None,
        enable_tree_stagnation_check: bool = False,
        tree_similarity_threshold: float = 0.9,
    ):
        """初始化反思Chain
        
        Args:
            reflector_agent: Reflector Agent
            state_manager: 状态管理器
            path_summarizer_agent: PathSummarizer Agent（可选）
            recorder_agent: Recorder Agent（可选）
        """
        self.reflector_agent = reflector_agent
        self.state_manager = state_manager
        self.path_summarizer_agent = path_summarizer_agent
        self.recorder_agent = recorder_agent
        self.enable_tree_stagnation_check = bool(enable_tree_stagnation_check)
        self._tree_checker = _UiTreeStagnationChecker(tree_similarity_threshold)
    
    def run(
        self,
        before_screenshot: Optional[str] = None,
        after_screenshot: Optional[str] = None,
        step: int = 0,
        enable_notetaker: bool = False
    ) -> Dict[str, Any]:
        """运行反思Chain
        
        Args:
            before_screenshot: 操作前的截图路径
            after_screenshot: 操作后的截图路径
            step: 当前步骤
            enable_notetaker: 是否启用Notetaker
            
        Returns:
            反思结果字典
        """
        # 准备图片
        images = []
        if before_screenshot:
            images.append(before_screenshot)
        if after_screenshot:
            images.append(after_screenshot)
        
        # 调用Reflector Agent
        result = self.reflector_agent.run(images)
        
        outcome = result.get('outcome', '')
        error_description = result.get('error_description', '')
        
        # 解析outcome
        if "S" in outcome : 
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
            tree_similarity, tree_confirmed, tree_before_xml, tree_after_xml = self._tree_checker.confirm(
                before_screenshot, after_screenshot
            )
            if tree_confirmed is True:
                final_outcome = "N"
            elif tree_confirmed is False:
                final_outcome = "S"
        
        # 获取当前状态
        state = self.state_manager.get_state()
        last_action = state.execution.last_action
        last_summary = state.execution.last_summary
        
        # 更新进度状态
        progress_status = state.planning.completed_plan_summary
        self.state_manager.set_progress_status(progress_status)
        
        # 追加动作记录
        self.state_manager.append_action(
            last_action,
            last_summary,
            final_outcome,
            error_description
        )
        
        # 路径摘要（每5步且操作成功时触发）
        path_summarizer_raw_response = None
        if (step + 1) % 5 == 0 and final_outcome == "S" and self.path_summarizer_agent:
            path_summarizer_raw_response = self._run_path_summarizer()
        
        # Recorder（仅在操作成功时执行）
        recorder_raw_response = None
        if final_outcome == "S" and enable_notetaker and self.recorder_agent:
            recorder_raw_response = self._run_recorder(after_screenshot)
        
        result['action_outcome'] = final_outcome
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
            "_recorder_raw_response": recorder_raw_response
        }
    
    def _run_path_summarizer(self) -> Any:
        """运行PathSummarizer"""
        if not self.path_summarizer_agent:
            return
            
        print("Running Path Summarizer...")
        result = self.path_summarizer_agent.run([])
        summary = result.get('summary', '')
        
        if summary:
            self.state_manager.set_completed_plan_summary(summary)
            print(f"Path summary updated: {summary}")
        
        return result.get("_raw_response")
            
    def _run_recorder(self, screenshot_path: str) -> Any:
        """运行Recorder"""
        if not self.recorder_agent or not screenshot_path:
            return
            
        print("Running Recorder...")
        result = self.recorder_agent.run([screenshot_path])
        important_notes = result.get('important_notes', '')
        
        if important_notes:
            self.state_manager.set_important_notes(important_notes)
            print(f"Important notes updated: {important_notes}")
        
        return result.get("_raw_response")

