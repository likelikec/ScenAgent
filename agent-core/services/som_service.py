"""Set-of-Mark (SoM) Service: Process screenshots with UI element marking"""
import os
import json
from typing import Dict, Tuple, Optional, Any, Union, List
from PIL import Image

try:
    from screen_perceptor.ssip.perceptor.screen_perception_AT import ScreenPerceptionAccessibilityTree
    from screen_perceptor.ssip.perceptor.tools import draw_transparent_boxes_with_labels
except (ImportError, ModuleNotFoundError) as e:
    import_error_msg = str(e)
    print(f"Warning: Could not import SoM dependencies: {import_error_msg}")
    if "loguru" in import_error_msg.lower():
        print("Hint: SoM mode requires 'loguru' package. Install it with: pip install loguru")
    ScreenPerceptionAccessibilityTree = None
    draw_transparent_boxes_with_labels = None


class SoMService:
    """Service for Set-of-Mark processing"""
    
    def __init__(self):
        """Initialize SoM service"""
        self.current_mapping: Dict[str, Any] = {}
        
        if ScreenPerceptionAccessibilityTree is None or draw_transparent_boxes_with_labels is None:
            raise ImportError(
                "SoM dependencies are not available. "
                "Please ensure screen_perceptor/ssip is properly set up. "
                "If you see 'loguru' errors, install it with: pip install loguru"
            )
    
    def process_screenshot(
        self,
        screenshot_path: str,
        xml_path: str,
        save_dir: str,
        target_app: Optional[str] = None
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Process screenshot with SoM marking
        
        Args:
            screenshot_path: Path to original screenshot
            xml_path: Path to UI hierarchy XML
            save_dir: Directory to save marked images (should be marked/ subfolder)
            target_app: Optional target app package name
            
        Returns:
            Tuple of (marked_image_path, mapping_json_path, som_mapping)
        """
        # Ensure save directory exists
        os.makedirs(save_dir, exist_ok=True)
        
        # Read XML
        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"XML file not found: {xml_path}")
        
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Parse accessibility tree
        at = ScreenPerceptionAccessibilityTree(xml_content, target_app=target_app)
        
        # Get nodes that need marking
        nodes_need_marked = at.get_nodes_need_marked(set_mark=True)
        
        mapping: Dict[str, Any] = {}
        for node_type in ("clickable", "scrollable"):
            centers = nodes_need_marked[node_type]["node_center_list"]
            bounds = nodes_need_marked[node_type]["node_bounds_list"]
            for mark, center in centers.items():
                mapping[str(mark)] = {
                    "center": list(center) if isinstance(center, tuple) else center,
                    "bounds": bounds.get(mark),
                    "node_type": node_type
                }
        
        self.current_mapping = mapping
        
        # Load and mark screenshot
        screenshot_image = Image.open(screenshot_path)
        
        # Mark clickable elements (red boxes, label at top-left)
        screenshot_image_marked = draw_transparent_boxes_with_labels(
            screenshot_image,
            nodes_need_marked["clickable"]["node_bounds_list"],
            label_position="top_left",
            box_color=(255, 0, 0, 180),
            font_box_background_color=(255, 0, 0, 160)
        )
        
        # Mark scrollable elements (green boxes, label at top-right)
        screenshot_image_marked = draw_transparent_boxes_with_labels(
            screenshot_image_marked,
            nodes_need_marked["scrollable"]["node_bounds_list"],
            label_position="top_right",
            box_color=(0, 255, 0, 180),
            font_box_background_color=(0, 255, 0, 160),
            line_width=5
        )
        
        # Generate save paths
        base_name = os.path.basename(screenshot_path)
        name_without_ext = os.path.splitext(base_name)[0]
        
        marked_image_path = os.path.join(save_dir, f"{name_without_ext}_marked.png")
        mapping_json_path = os.path.join(save_dir, f"{name_without_ext}_mapping.json")
        
        # Save marked image
        screenshot_image_marked.convert("RGB").save(marked_image_path)
        
        # Save mapping JSON
        self.save_mapping_json(self.current_mapping, mapping_json_path)
        
        return marked_image_path, mapping_json_path, self.current_mapping
    
    def get_som_mapping(self) -> Dict[str, Any]:
        """Get current SoM mapping
        
        Returns:
            Dictionary mapping mark strings to coordinates
        """
        return self.current_mapping
    
    def save_mapping_json(self, mapping: Dict[str, Any], save_path: str) -> None:
        """Save mapping to JSON file
        
        Args:
            mapping: Mark to coordinate mapping
            save_path: Path to save JSON file
        """
        # Convert tuple coordinates to lists for JSON serialization
        json_mapping = {k: list(v) if isinstance(v, (tuple, list)) else v 
                       for k, v in mapping.items()}
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(json_mapping, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load_mapping_json(json_path: str) -> Dict[str, Any]:
        """Load mapping from JSON file
        
        Args:
            json_path: Path to mapping JSON file
            
        Returns:
            Dictionary mapping mark strings to coordinates
        """
        if not os.path.exists(json_path):
            return {}
        
        with open(json_path, 'r', encoding='utf-8') as f:
            json_mapping = json.load(f)
        
        mapping: Dict[str, Any] = {}
        for k, v in json_mapping.items():
            if isinstance(v, list):
                mapping[str(k)] = tuple(v)
                continue
            if isinstance(v, dict):
                center = v.get("center")
                if isinstance(center, list):
                    v["center"] = tuple(center)
                mapping[str(k)] = v
                continue
            mapping[str(k)] = v
        return mapping

