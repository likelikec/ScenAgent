from copy import deepcopy

from ..screen_AT import ScreenAccessibilityTree


class ScreenPerceptionAccessibilityTree(ScreenAccessibilityTree):
    def __init__(self, at_xml: str, target_app: None):
        super().__init__(at_xml, target_app)

    def get_nodes_need_visual_desc(self):
        node_bounds_list = []
        def _need_visual_filter(node):
            # 如果是叶子节点且类名为 ImageView 或 View，则需要视觉描述
            if len(node['children']) == 0 and node['class'] in ['android.widget.ImageView', 'android.view.View']:
                node_bounds_list.append(node['bounds'])
            return node

        for at_node in self.at_dict:
            self._common_filter(at_node, _need_visual_filter)
        return node_bounds_list

    def set_visual_desc_to_nodes(self, desc_map):
        index = 0
        def _need_visual_filter(node):
            nonlocal index
            # 如果是叶子节点且类名为 ImageView 或 View，则需要视觉描述
            if len(node['children']) == 0 and node['class'] in ['android.widget.ImageView', 'android.view.View']:
                node['text'] = desc_map[index]
                index = index + 1
            return node

        self.at_dict = [self._common_filter(at_node, _need_visual_filter) for at_node in self.at_dict]

    def get_nodes_need_marked(self, set_mark=False):
        def _area(bounds):
            if not bounds or len(bounds) != 2:
                return 0
            w = max(0, bounds[1][0] - bounds[0][0])
            h = max(0, bounds[1][1] - bounds[0][1])
            return w * h

        screen_right = 0
        screen_bottom = 0
        for at_node in self.at_dict:
            b = at_node.get("bounds")
            if b and len(b) == 2:
                screen_right = max(screen_right, b[1][0])
                screen_bottom = max(screen_bottom, b[1][1])
        screen_area = max(1, screen_right * screen_bottom)

        def _is_fullscreen_like(node):
            return _area(node.get("bounds")) / screen_area >= 0.85

        def _is_semantic_enough(node):
            if node.get("text"):
                return True
            rid = node.get("resource-id")
            if rid:
                return True
            desc = node.get("content-desc")
            if desc:
                return True
            return False

        def _should_keep_clickable(node):
            if not _is_fullscreen_like(node):
                return True
            return _is_semantic_enough(node)

        candidates = []

        def walk(node):
            props = node.get("properties") or []
            if "clickable" in props:
                if _should_keep_clickable(node):
                    candidates.append(("clickable", node))
            elif "scrollable" in props:
                candidates.append(("scrollable", node))
            for child in node.get("children", []) or []:
                walk(child)

        for at_node in self.at_dict:
            walk(at_node)

        index = 0
        nodes_need_marked = {
            "clickable": {
                'node_bounds_list': {},
                'node_center_list': {}
            },
            "scrollable": {
                'node_bounds_list': {},
                'node_center_list': {}
            }
        }

        seen_bounds = {"clickable": set(), "scrollable": set()}
        seen_center = {"clickable": set(), "scrollable": set()}

        for node_type, node in candidates:
            bounds = node.get("bounds")
            center = node.get("center")
            if not bounds or not center:
                continue
            bounds_key = tuple(map(tuple, bounds))
            center_key = tuple(center)
            if bounds_key in seen_bounds[node_type] or center_key in seen_center[node_type]:
                continue
            seen_bounds[node_type].add(bounds_key)
            seen_center[node_type].add(center_key)
            if set_mark:
                node["mark"] = index
            nodes_need_marked[node_type]['node_bounds_list'][index] = bounds
            nodes_need_marked[node_type]['node_center_list'][index] = center
            index += 1

        return nodes_need_marked

    async def _summarize_clickable_nodes(self, at_node, summarize_text_func):
        # 检查节点是否包含 'clickable' 属性
        def _is_node_clickable(node):
            return ('properties' in node and "clickable" in node['properties']) or ('merged-properties' in node and any('clickable' in props for props in node['merged-properties']))

        # 用于递归移除所有不包含 'clickable' 属性，且其所有子孙节点都不包含 'clickable' 的节点。
        def _prune_non_clickable(node):
            if 'children' not in node or len(node['children']) == 0: # 终止条件：没有 children
                return node if _is_node_clickable(node) else None
            pruned_children = []
            for child in node['children']:
                if _is_node_clickable(child):
                    pruned_children.append(child) # 子节点可以点击则不处理
                else:
                    pruned_child = _prune_non_clickable(child) # 递归处理子节点
                    if pruned_child is not None:
                        pruned_children.append(pruned_child)
            node['children'] = pruned_children
            if pruned_children or _is_node_clickable(node): # 当前节点是否保留
                return node
            return None
        # 遍历所有clickable节点
        node_successor_list = []
        def _clickable_filter(node):
            if _is_node_clickable(node):
                node_successor_list.append(deepcopy(node["children"]) if 'children' in node else [])
                node = _prune_non_clickable(node)  # 移除其下所有不包含 'clickable' 属性的节点
            return node
        at_node = self._common_filter(at_node, _clickable_filter)
        # 总结节点
        summarized_text_map = await summarize_text_func(node_successor_list)
        # 二次遍历所有clickable节点，添加总结
        index = 0
        def _clickable_filter(node):
            nonlocal index
            if _is_node_clickable(node):
                if summarized_text_map[index] is not None:
                    node["text"] = summarized_text_map[index]
                index = index + 1
            return node
        at_node = self._common_filter(at_node, _clickable_filter)
        return at_node

    async def get_page_description(self, summarize_text_func=None):
        page_desc = []
        for at_node in self.at_dict:
            at_node = self._common_filter(at_node, self._coordinate_filter)
            at_node = self._common_filter(at_node, self._redundant_info_filter)
            at_node = self._struct_compress(at_node)
            if summarize_text_func is not None:
                at_node = await self._summarize_clickable_nodes(at_node, summarize_text_func)
            page_desc.append("\n".join(self._format_ui_tree(at_node)))
        return page_desc

    # 结构压缩，必须在冗余信息过滤后才能执行（有强假设）
    def _struct_compress(self, node):
        def merge_info(parent, child):
            if 'center' in parent and 'center' in child: # 均有坐标信息，说明均可点击，不能合并这种节点
                return parent
            elif 'center' in parent: # 父亲有坐标信息，说明可点击，将坐标信息传递给孩子留存
                child['bounds'] = parent['bounds']
                child['center'] = parent['center']

            # 初始化 merged 字段
            for key in ['class', 'resource-id', 'properties']:
                if key in parent:
                    child.setdefault(f'merged-{key}', [])
                    if parent[key] not in child[f'merged-{key}']:
                        child[f'merged-{key}'].append(parent[key])
            return child

        # 如果没有 children 或不是列表，直接返回
        if not isinstance(node, dict):
            return node
        children = node.get('children')
        if not isinstance(children, list):
            return node

        # 压缩当前节点
        while len(children) == 1:
            child = children[0]
            child = merge_info(node, child)
            node = child
            children = node.get('children', [])

        # 对每个子节点递归压缩
        if 'children' in node:
            node['children'] = [self._struct_compress(child) for child in node['children']]

        return node

    def _format_ui_tree(self, node, indent=0):
        lines = []

        # 合并 class 信息
        base_class = node.get('class', 'Unknown')
        merged_classes = node.get('merged-class', [])
        full_class = "/".join(merged_classes + [base_class]) if merged_classes else base_class

        # 合并 resource-id 信息
        base_id = node.get('resource-id')
        merged_ids = node.get('merged-resource-id', [])
        full_id = "/".join(merged_ids + [base_id]) if base_id and merged_ids else base_id

        # 合并属性（properties 和 merged-properties）
        props = set(node.get('properties', []))
        merged_props = node.get('merged-properties', [])
        for mp in merged_props:
            if isinstance(mp, list):
                props.update(mp)
            else:
                props.add(mp)
        props_text = f"[{', '.join(sorted(props))}]" if props else ""

        # 中心坐标
        center = node.get('center')
        center_text = f"[Center: {center}]" if center else ""

        # 文本内容
        text = node.get('text')
        text_text = f"[{text}]" if text else ""

        # 构建当前节点的描述
        desc_parts = [full_class]
        if full_id:
            desc_parts.append(f"({full_id})")
        if text_text:
            desc_parts.append(text_text)
        if center_text:
            desc_parts.append(center_text)
        if props_text:
            desc_parts.append(props_text)

        # 输出行
        line = "  " * indent + "- " + " ".join(desc_parts)
        lines.append(line)

        # 递归子节点
        for child in node.get('children', []):
            lines.extend(self._format_ui_tree(child, indent + 1))

        return lines

    # [生成页面描述时] 非可点击/滚动的元素无需提供坐标信息
    @staticmethod
    def _coordinate_filter(node):
        # if not any(k in node['properties'] for k in ('clickable', 'long-clickable', 'scrollable')):
        if 'clickable' not in node['properties'] and 'long-clickable' not in node['properties']:
            del node['bounds']
            del node['center']
        return node

    # [生成页面描述时] 清理冗余信息
    @staticmethod
    def _redundant_info_filter(node):
        # 删除不必要的信息，例如包名
        del node['package']
        del node['layer']
        # 简化不必要的类名
        node['class'] = node['class'].split('.')[-1].replace("ImageView", "Img").replace("TextView", "Txt")
        # 简化不必要的资源ID
        if node['resource-id'] is None:
            del node['resource-id']
        else:
            node['resource-id'] = node['resource-id'].split('/')[-1]
        # 删除不必要的属性
        for key in list(node['properties']):
            if key in ['enabled', 'visible-to-user']:
                node['properties'].remove(key)
        # 删除空的属性
        if not node['properties']:
            del node['properties']
        # 删除空的文本信息
        if not node.get('text'):
            del node['text']
        # 删除空的子节点
        if len(node['children']) == 0 :
            del node['children']
        return node

