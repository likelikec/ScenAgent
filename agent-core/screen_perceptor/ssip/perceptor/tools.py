from PIL import Image, ImageDraw, ImageFont
import numpy as np

# 在图像上绘制透明矩形框，并显示标记编号
def draw_transparent_boxes_with_labels(
    image_input,
    boxes_dict,
    label_position='top_left',
    box_color=(255, 0, 0, 180),
    text_color=(255, 255, 255, 255),
    font_size=40,
    font_box_padding=10,
    font_box_background_color=(0, 0, 0, 160),
    line_width=10,
    font_path=None,
):
    if isinstance(image_input, np.ndarray):
        image = Image.fromarray(image_input).convert("RGBA")
    else:
        image = image_input.convert("RGBA")

    try:
        font = ImageFont.truetype(font_path or "arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    result = image.copy()

    def _box_area(coords):
        (x1, y1), (x2, y2) = coords
        return max(0, x2 - x1) * max(0, y2 - y1)

    items = list(boxes_dict.items())
    items.sort(key=lambda it: (_box_area(it[1]), str(it[0])))

    for label, coords in items: # 遍历每一个框，label是框的编号0、1、2...
        (x1, y1), (x2, y2) = coords

        # 计算区域范围（考虑线宽和标签）
        text = str(label)
        temp_draw = ImageDraw.Draw(Image.new("RGBA", result.size))
        text_bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        if label_position == 'top_right':
            bg_x1 = x2 - text_width - font_box_padding * 2
            bg_x2 = x2
        elif label_position == 'top_left':
            bg_x1 = x1
            bg_x2 = x1 + text_width + font_box_padding * 2
        else:
            raise RuntimeError("Unsupported label position. Use 'top_left' or 'top_right'.")

        bg_y1 = y1
        bg_y2 = y1 + text_height + font_box_padding * 2

        min_x = min(x1 - line_width, bg_x1)
        min_y = min(y1 - line_width, bg_y1)
        max_x = max(x2 + line_width, bg_x2)
        max_y = max(y2 + line_width, bg_y2)

        # 从当前结果图中提取这个区域的背景（避免后画的大框覆盖前画的小框）
        background_crop = result.crop((min_x, min_y, max_x, max_y))

        # 在提取的背景上画框和标签
        overlay = Image.new("RGBA", background_crop.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 框
        draw.rectangle(
            [x1 - min_x, y1 - min_y, x2 - min_x, y2 - min_y],
            outline=box_color,
            width=line_width
        )

        # 标签背景
        draw.rectangle(
            [bg_x1 - min_x, bg_y1 - min_y, bg_x2 - min_x, bg_y2 - min_y],
            fill=font_box_background_color
        )

        # 文字
        text_x = bg_x1 - min_x + font_box_padding
        text_y = bg_y1 - min_y + font_box_padding
        draw.text((text_x, text_y), text, fill=text_color, font=font)

        # 合成 overlay 到 background_crop
        composed_crop = Image.alpha_composite(background_crop, overlay)

        # 最终贴回 result
        result.paste(composed_crop, (min_x, min_y))

    return result

