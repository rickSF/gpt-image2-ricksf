"""
gpt-image2-ricksf - GPT Image 2 生图节点插件
支持汇取云和 Runninghub 两大 API 生图渠道
- 汇取云：gpt-image-2 ¥0.068/次（文生图）
- Runninghub：¥0.1/次（文生图/图生图）

汇取云图生图需要先上传图片到 Runninghub 获取 URL

有参考图自动选择图生图，无参考图自动选择文生图

作者：@ricksf
版本：v2.0.1
"""

from .gpt_image_2_comprehensive_node import (
    NODE_CLASS_MAPPINGS as GPT_IMAGE2_COMP_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as GPT_IMAGE2_COMP_DISPLAY_MAPPINGS
)

# 只保留综合版节点
NODE_CLASS_MAPPINGS = {
    **GPT_IMAGE2_COMP_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **GPT_IMAGE2_COMP_DISPLAY_MAPPINGS,
}

WEB_DIRECTORY = "./web"
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

print("=" * 60)
print("  🎨 gpt-image2-ricksf 节点加载完成!")
print("=" * 60)
print(f"  🙅 GPT Image 2 综合版：{len(NODE_CLASS_MAPPINGS)} 个节点")
print(f"  🌐 API渠道：汇取云 / Runninghub")
print(f"  💰 汇取云：gpt-image-2 ¥0.068/次（文生图/图生图）")
print(f"  💰 Runninghub：¥0.1/次（文生图/图生图）")
print(f"  👨‍🏫 作者：@ricksf")
print("=" * 60)