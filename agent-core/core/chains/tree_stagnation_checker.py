import os
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    import xmltodict
except ImportError:
    xmltodict = None


class UiTreeStagnationChecker:
    def __init__(self, tree_similarity_threshold: float = 0.9):
        self.tree_similarity_threshold = float(tree_similarity_threshold or 0.0)

    def confirm(
        self,
        before_screenshot: Optional[str],
        after_screenshot: Optional[str],
    ) -> Tuple[Optional[float], Optional[bool], Optional[str], Optional[str]]:
        if not before_screenshot or not after_screenshot or xmltodict is None:
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
        return xml_path if os.path.exists(xml_path) else None

    def _extract_ui_tokens(self, xml_path: str) -> List[str]:
        try:
            with open(xml_path, "r", encoding="utf-8") as f:
                parsed = xmltodict.parse(f.read())
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
        pkg = self._get_attr(node, "package")
        cls = self._get_attr(node, "class")
        res_id = self._get_attr(node, "resource-id")
        text = self._normalize_text(self._get_attr(node, "text"))
        content_desc = self._normalize_text(self._get_attr(node, "content-desc"))
        hint = self._normalize_text(self._get_attr(node, "hint"))
        bounds = self._get_attr(node, "bounds")
        flags = ",".join(
            f for f, v in [
                ("clickable", self._get_attr(node, "clickable")),
                ("scrollable", self._get_attr(node, "scrollable")),
                ("editable", self._get_attr(node, "editable")),
                ("checkable", self._get_attr(node, "checkable")),
                ("checked", self._get_attr(node, "checked")),
                ("enabled", self._get_attr(node, "enabled")),
                ("selected", self._get_attr(node, "selected")),
                ("focused", self._get_attr(node, "focused")),
            ]
            if v == "true"
        )
        if not primary_package or not pkg or pkg == primary_package:
            tokens.append("|".join([
                cls,
                res_id,
                text[:80] if text else "",
                content_desc[:80] if content_desc else "",
                hint[:80] if hint else "",
                bounds,
                flags,
            ]))
        children = node.get("node")
        if children is not None:
            self._collect_tokens_from_node(children, tokens, primary_package)

    def _infer_primary_package(self, node: Any) -> str:
        counts: Dict[str, int] = {}
        self._collect_package_counts(node, counts)
        if not counts:
            return ""
        return max(counts.items(), key=lambda item: item[1])[0]

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
