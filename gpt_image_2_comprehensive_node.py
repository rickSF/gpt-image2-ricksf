import math
import time
import json
import base64
import os
import urllib.request
import urllib.error
import torch
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import numpy as np
from io import BytesIO
from PIL import Image
import comfy.utils
from comfy.utils import common_upscale

# ============================================================
# API 配置
# ============================================================
HUIQU_BASE_URL = "https://api.bjhuiqu.net/v1"
RUNNINGHUB_BASE_URL = "https://www.runninghub.cn/openapi/v2"

# 获取节点目录和配置文件路径
NODE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(NODE_DIR, "config.json")


def load_config():
    """从 config.json 加载配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[综合节点] 读取配置文件失败: {e}")
    return {}


def save_config(config):
    """保存配置到 config.json"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[综合节点] 配置已保存到 {CONFIG_FILE}")
    except Exception as e:
        print(f"[综合节点] 保存配置文件失败: {e}")

# 创建带重试的 session
_session = requests.Session()
_retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
_adapter = HTTPAdapter(max_retries=_retry)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)


def tensor2pil(image):
    return [Image.fromarray(np.clip(255.0 * img.cpu().numpy().squeeze(), 0, 255).astype(np.uint8)) for img in image]


def pil2tensor(image):
    if image.mode != "RGB":
        image = image.convert("RGB")
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)


def downscale_input(image):
    samples = image.movedim(-1, 1)
    total_pixels = int(1536 * 1024)
    scale_by = math.sqrt(total_pixels / (samples.shape[3] * samples.shape[2]))
    if scale_by >= 1:
        return image
    width = round(samples.shape[3] * scale_by)
    height = round(samples.shape[2] * scale_by)
    scaled = common_upscale(samples, width, height, "lanczos", "disabled")
    return scaled.movedim(1, -1)


class DapaoGPTImage2ComprehensiveNode:
    """GPT Image 2 综合节点
    支持汇取云和 Runninghub 两大 API 生图渠道

    - 汇取云：gpt-image-2 ¥0.068/次（仅文生图）
    - Runninghub：文生图/图生图 ¥0.1/次

    有参考图自动选择图生图，无参考图自动选择文生图
    """
    _last_generated_image_urls = ""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "🌐 API渠道": (["汇取云", "Runninghub"], {"default": "汇取云"}),
                "🔑 API密钥": ("STRING", {"default": "", "password": True}),
                "📝 提示词": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "🖼️ 参考图1": ("IMAGE",),
                "🖼️ 参考图2": ("IMAGE",),
                "🖼️ 参考图3": ("IMAGE",),
                "🖼️ 参考图4": ("IMAGE",),
                "📐 比例": (["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9"], {"default": "auto"}),
                "🖼️ 分辨率": (["1k", "2k", "4k"], {"default": "1k"}),
                "🤖 模型": (["gpt-image-2", "gpt-image-2-FL", "gpt-image-2「备用」"], {"default": "gpt-image-2"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("🖼️ 图像", "📋 响应信息", "🔗 图片链接", "💬 历史记录")
    FUNCTION = "process"
    CATEGORY = "🤖ricksf/GPT"
    DESCRIPTION = "GPT Image 2 综合版 @ricksf"

    def __init__(self):
        self.timeout = 900

    def _blank_tensor(self):
        blank = Image.new("RGB", (1024, 1024), color="white")
        return pil2tensor(blank)

    def _download_image(self, url, timeout=60):
        import urllib.request

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                img_data = resp.read()
            print(f"[综合节点] 下载图片 大小: {len(img_data)} bytes")

            img = Image.open(BytesIO(img_data)).convert("RGB")
            img_array = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_array)[None]
            print(f"[综合节点] 图片尺寸: {img.size}, tensor shape: {img_tensor.shape}")
            return img_tensor
        except Exception as e:
            print(f"[综合节点] 下载图片失败 {url}: {e}")
            return None

    def _image_to_base64(self, image_tensor):
        """将 IMAGE tensor 转换为 base64 data URI"""
        # 直接转换，不做缩放，与参考代码一致
        img_array = image_tensor[0].cpu().numpy()  # shape: [H, W, C]
        img_array = (img_array * 255).clip(0, 255).astype(np.uint8)
        img_pil = Image.fromarray(img_array)
        if img_pil.mode != "RGB":
            img_pil = img_pil.convert("RGB")
        from io import BytesIO
        buf = BytesIO()
        img_pil.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _huiqu_generate(self, api_key, model, prompt, pbar):
        """汇取云生图（仅文生图）"""
        import urllib.request
        import urllib.parse

        url = f"{HUIQU_BASE_URL}/images/generations"
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "auto",
            "response_format": "url"
        }

        print(f"[汇取云] 发送请求...")
        print(f"[汇取云] URL: {url}")
        print(f"[汇取云] Model: {model}")

        json_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=json_data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key.strip()}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"[汇取云] HTTP错误: {e.code} - {e.reason}")
            error_body = e.read().decode("utf-8") if e.fp else ""
            print(f"[汇取云] 错误响应: {error_body[:500]}")
            return None, f"API请求失败: {e.code} {e.reason}"
        except Exception as e:
            print(f"[汇取云] 请求异常: {e}")
            return None, f"请求异常: {str(e)}"

        print(f"[汇取云] 响应: {json.dumps(result, ensure_ascii=False)[:500]}")

        # 提取图片URL
        image_url = None
        if "data" in result and len(result["data"]) > 0:
            image_url = result["data"][0].get("url", "")
        if not image_url:
            # 尝试其他可能的字段
            image_url = result.get("url") or result.get("image_url") or result.get("output_url", "")

        if not image_url:
            return None, f"未获取到图片URL: {result}"

        pbar.update_absolute(70)
        tensor = self._download_image(image_url)
        if tensor is None:
            return None, "图片下载失败"

        return tensor, f"成功 | 汇取云 | {model} | {image_url[:50]}..."

    def _runninghub_submit(self, api_key, prompt, image_urls, aspect_ratio, resolution, is_img2img, api_source="Runninghub"):
        """提交 Runninghub 任务"""
        import urllib.request
        import urllib.parse

        # Runninghub 不支持 "auto" 和 "3:2", "2:3", "3:4", "9:21"，需要转换
        if api_source == "Runninghub":
            valid_ratios = ["3:2", "1:1", "2:3", "5:4", "4:5", "16:9", "9:16", "21:9", "3:4", "4:3", "9:21"]
            if aspect_ratio == "auto" or aspect_ratio not in valid_ratios:
                aspect_ratio = "1:1"  # 默认使用 1:1

        payload = {
            "prompt": prompt.strip(),
            "aspectRatio": aspect_ratio,
            "resolution": resolution
        }
        if is_img2img:
            submit_url = f"{RUNNINGHUB_BASE_URL}/rhart-image-g-2/image-to-image"
            payload["imageUrls"] = image_urls
            print(f"[Runninghub 图生图] 提交URL: {submit_url}")
        else:
            submit_url = f"{RUNNINGHUB_BASE_URL}/rhart-image-g-2/text-to-image"
            print(f"[Runninghub 文生图] 提交URL: {submit_url}")

        print(f"[Runninghub] prompt: {prompt[:80]}...")
        print(f"[Runninghub] aspectRatio={aspect_ratio}, resolution={resolution}")
        if is_img2img:
            print(f"[Runninghub] 参考图数量: {len(image_urls)}")

        json_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            submit_url,
            data=json_data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key.strip()}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            print(f"[Runninghub] HTTP错误: {e.code} - {error_body[:500]}")
            return None, f"HTTP {e.code}: {error_body[:200]}"
        except Exception as e:
            print(f"[Runninghub] 提交异常: {e}")
            return None, f"提交异常: {str(e)}"

        print(f"[Runninghub] 提交响应: {json.dumps(result, ensure_ascii=False)[:500]}")

        # 响应可能直接包含 status 和 results（成功时）
        task_id = result.get("taskId", "")
        if not task_id:
            return None, f"无taskId: {result}"

        return task_id, None

    def _runninghub_query(self, api_key, task_id):
        """查询 Runninghub 任务"""
        import urllib.request

        query_url = f"{RUNNINGHUB_BASE_URL}/query"
        payload = {"taskId": task_id}

        json_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            query_url,
            data=json_data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key.strip()}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return None, f"查询HTTP {e.code}: {error_body[:200]}"
        except Exception as e:
            return None, f"查询异常: {str(e)}"

        print(f"[Runninghub 查询] 响应: {json.dumps(result, ensure_ascii=False)[:500]}")

        return result, None

    def _extract_result_url(self, result):
        """从查询结果中提取图片URL"""
        results = result.get("results", [])
        if not results:
            return None
        first = results[0]
        return first.get("url") or first.get("outputUrl") or first.get("download_url")

    def process(self, **kwargs):
        api_source = kwargs.get("🌐 API渠道", "汇取云")
        api_key_input = kwargs.get("🔑 API密钥", "")
        prompt = kwargs.get("📝 提示词", "")
        model = kwargs.get("🤖 模型", "gpt-image-2")
        aspect_ratio = kwargs.get("📐 比例", "auto")
        resolution = kwargs.get("🖼️ 分辨率", "1k")

        # 获取参考图（最多4张）
        input_images = [
            kwargs.get("🖼️ 参考图1"),
            kwargs.get("🖼️ 参考图2"),
            kwargs.get("🖼️ 参考图3"),
            kwargs.get("🖼️ 参考图4"),
        ]
        # 只保留非空的参考图
        valid_images = [img for img in input_images if img is not None]
        is_img2img = len(valid_images) > 0

        blank_tensor = self._blank_tensor()

        # API Key 获取逻辑：根据渠道获取对应的 Key
        config = load_config()
        if api_source == "汇取云":
            api_key = config.get("huiqu_api_key", "").strip()
            if not api_key:
                api_key = api_key_input.strip()
            key_saved_name = "huiqu_api_key"
        else:
            api_key = config.get("runninghub_api_key", "").strip()
            if not api_key:
                api_key = api_key_input.strip()
            key_saved_name = "runninghub_api_key"

        if not api_key:
            return (blank_tensor, "API密钥为空", "", "")

        if not prompt.strip():
            return (blank_tensor, "提示词为空", "", "")

        try:
            pbar = comfy.utils.ProgressBar(100)
            pbar.update_absolute(10)

            result_info = ""
            image_tensor = None

            if api_source == "汇取云":
                # 汇取云仅支持文生图，有参考图则提示用户
                if is_img2img:
                    return (blank_tensor, "汇取云仅支持文生图，请使用 Runninghub 图生图（有参考图自动切换）", "", "")
                image_tensor, result_info = self._huiqu_generate(api_key, model, prompt, pbar)

            elif api_source == "Runninghub":
                # 构建参考图 URL 列表
                image_urls = []

                if is_img2img:
                    # 将参考图转为 base64
                    for img in valid_images:
                        image_base64 = self._image_to_base64(img)
                        image_urls.append(f"data:image/png;base64,{image_base64}")
                    print(f"[Runninghub] 已转换 {len(image_urls)} 张参考图为 base64")

                # 提交任务
                task_id, error = self._runninghub_submit(api_key, prompt, image_urls, aspect_ratio, resolution, is_img2img, api_source)

                if error:
                    return (blank_tensor, f"提交失败: {error}", "", "")

                print(f"[Runninghub] 任务提交成功 taskId={task_id}")

                # 轮询
                pbar.update_absolute(30)
                max_wait = 180
                waited = 0

                while True:
                    time.sleep(5)
                    waited += 5

                    result, error = self._runninghub_query(api_key, task_id)
                    if error:
                        return (blank_tensor, f"查询失败: {error}", "", "")

                    status = result.get("status", "").upper()
                    print(f"[Runninghub] 状态: {status}, 等待: {waited}s")

                    if status == "SUCCESS":
                        image_url = self._extract_result_url(result)
                        if not image_url:
                            return (blank_tensor, f"成功但无URL: {result}", "", "")

                        pbar.update_absolute(80)
                        image_tensor = self._download_image(image_url)
                        if image_tensor is None:
                            return (blank_tensor, "图片下载失败", "", "")

                        mode = "图生图" if is_img2img else "文生图"
                        result_info = f"成功 | Runninghub{mode} | {aspect_ratio} | {resolution} | {image_url[:50]}..."
                        break

                    if status in ("FAILED", "FAIL"):
                        error_msg = result.get("errorMessage") or result.get("msg") or "未知错误"
                        return (blank_tensor, f"任务失败: {error_msg}", "", "")

                    if waited >= max_wait:
                        return (blank_tensor, f"超时 {waited}s, 状态: {status}", "", "")

                    pbar.update_absolute(min(70, 30 + int(waited * 0.2)))

            pbar.update_absolute(100)

            if image_tensor is not None:
                # 自动保存成功的 API Key 到本地
                if api_key_input.strip() and api_key_input.strip() != config.get(key_saved_name, ""):
                    config[key_saved_name] = api_key_input.strip()
                    save_config(config)

                # 更新历史
                if DapaoGPTImage2ComprehensiveNode._last_generated_image_urls:
                    DapaoGPTImage2ComprehensiveNode._last_generated_image_urls += "\n" + result_info
                else:
                    DapaoGPTImage2ComprehensiveNode._last_generated_image_urls = result_info

                history = DapaoGPTImage2ComprehensiveNode._last_generated_image_urls
                return (image_tensor, result_info, result_info.split("|")[-1].strip(), history)

            return (blank_tensor, result_info if result_info else "生成失败", "", "")

        except Exception as e:
            error_msg = f"执行失败: {str(e)}"
            print(f"[综合节点] {error_msg}")
            return (blank_tensor, error_msg, "", "")


NODE_CLASS_MAPPINGS = {
    "🙅GPT_image_2_综合@ricksf": DapaoGPTImage2ComprehensiveNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "🙅GPT_image_2_综合@ricksf": "🙅GPT_image_2_综合@ricksf",
}