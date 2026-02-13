from ...entity import ScreenPerceptionInfo


class SSIPInfo(ScreenPerceptionInfo):
    def __init__(self, width, height, perception_infos, non_visual_mode, SoM_mapping):
        self.non_visual_mode = non_visual_mode
        self.SoM_mapping = SoM_mapping

        super().__init__(width, height, perception_infos, use_set_of_marks_mapping=not self.non_visual_mode)

    def _perception_infos_to_str(self):
        return f"- Raw UI Hierarchy XML:\n"\
               f"{self.infos[0]}\n\n" \
               f"- Page Description:\n" \
               f"{self.infos[1]}\n\n"

    def _keyboard_prompt(self, extra_suffix=None):
        prompt = f"- Keyboard Status {'for '+extra_suffix if extra_suffix else ''}: " \
                 f"{'The keyboard has been activated and you can type.' if self.keyboard_status else 'The keyboard has not been activated and you can not type.'}\n" \
                 f"\n"
        return prompt

    def convert_marks_to_coordinates(self, mark):
        return self.SoM_mapping.get(mark, None)

    def get_screen_info_prompt(self, extra_suffix=None):
        prompt = ""
        if self.non_visual_mode:
            prompt = f"- Screen Structure Textualized Description {'for '+extra_suffix if extra_suffix else ''}: \n"
            prompt += f"{self.infos[1]}\n\n"
        prompt += self._keyboard_prompt(extra_suffix)

        return prompt

    def get_screen_info_note_prompt(self, description_prefix):
        prompt = f"{description_prefix}, with a width and height of {self.width} and {self.height} pixels respectively.\n"
        if self.non_visual_mode:
            prompt += f"To help imagine the screen, we provide Structure Textualized Description about the screen, which is written as a sort of Markdown. For scrollable and clickable elements, we provide the center attribute, whose value is the center coordinates of the current element on the screen in the format [x, y]: \n"
        else:
            prompt += f"We have provided an image of the screen and labeled all clickable elements using red boxes. You can indicate which element you want to action by the number in the upper left corner of the red box. For scrollable areas, we mark them with green boxes. You can indicate which area you want to scroll by using the number in the upper right corner of the green box.\n"
        return prompt

