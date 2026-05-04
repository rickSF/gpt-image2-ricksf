import math
import time
import json
import base64
import os
import urllib.request
import urllib.error
import torch
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
            print(f"[ricksf节点] 读取配置文件失败: {e}")
    return {}


def save_config(config):
    """保存配置到 config.json"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[ricksf节点] 配置已保存到 {CONFIG_FILE}")
    except Exception as e:
        print(f"[ricksf节点] 保存配置文件失败: {e}")


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


class RicksfGPTImage2ComprehensiveNode:
    """GPT Image 2 综合节点 @ricksf
    支持汇取云和 Runninghub 两大 API 生图渠道

    - 汇取云：gpt-image-2 ¥0.068/次（文生图/图生图）
    - Runninghub：¥0.1/次（文生图/图生图）

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
                "📐 比例": (["1024x1024", "1536x1024", "1024x1536", "2048x2048", "2048x1152", "3840x2160", "2160x3840", "1920x1080", "1080x1920", "1:1", "16:9", "9:16", "4:3", "3:4", "21:9"], {"default": "1024x1024"}),
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
        self.timeout = 360  # 6分钟超时

    def _blank_tensor(self):
        blank = Image.new("RGB", (1024, 1024), color="white")
        return pil2tensor(blank)

    def _download_image(self, url, timeout=60):
        import urllib.request

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                img_data = resp.read()
            print(f"[ricksf节点] 下载图片 大小: {len(img_data)} bytes")

            img = Image.open(BytesIO(img_data)).convert("RGB")
            img_array = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_array)[None]
            print(f"[ricksf节点] 图片尺寸: {img.size}, tensor shape: {img_tensor.shape}")
            return img_tensor
        except Exception as e:
            print(f"[ricksf节点] 下载图片失败 {url}: {e}")
            return None

    def _image_to_base64(self, image_tensor):
        """将 IMAGE tensor 转换为 base64（不含 data URI 前缀）"""
        img_array = image_tensor[0].cpu().numpy()  # [H, W, C], range [0, 1]
        img_array = (img_array * 255).clip(0, 255).astype(np.uint8)
        img_pil = Image.fromarray(img_array, mode='RGB')
        buf = BytesIO()
        img_pil.save(buf, format='PNG')
        b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        print(f"[ricksf节点] 图片转换: shape={img_array.shape}, base64长度={len(b64_str)}")
        return b64_str

    def _upload_image_to_runninghub(self, image_tensor, api_key):
        """上传图片到 Runninghub，返回 download_url"""
        import urllib.request

        img_array = image_tensor[0].cpu().numpy()
        img_array = (img_array * 255).clip(0, 255).astype(np.uint8)
        img_pil = Image.fromarray(img_array)
        if img_pil.mode != "RGB":
            img_pil = img_pil.convert("RGB")

        # 保存为临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img_pil.save(tmp.name, "PNG")
            tmp_path = tmp.name

        try:
            # 上传图片
            with open(tmp_path, "rb") as f:
                img_data = f.read()

            boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            body = f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"image.png\"\r\nContent-Type: image/png\r\n\r\n".encode() + img_data + f"\r\n--{boundary}--\r\n".encode()

            req = urllib.request.Request(
                f"{RUNNINGHUB_BASE_URL}/media/upload/binary",
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key.strip()}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                }
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            print(f"[ricksf节点] 上传图片响应: {json.dumps(result, ensure_ascii=False)[:300]}")

            if result.get("code") == 0 and result.get("data", {}).get("download_url"):
                return result["data"]["download_url"]
            return None
        except Exception as e:
            print(f"[ricksf节点] 上传图片失败: {e}")
            return None
        finally:
            os.unlink(tmp_path)

    def _huiqu_generate(self, api_key, model, prompt, aspect_ratio, image_base64_list, is_img2img, pbar):
        """汇取云生图（文生图/图生图）
        - 文生图：application/json
        - 图生图：application/json（image 字段为 base64 字符串数组）
        """
        import urllib.request

        url = f"{HUIQU_BASE_URL}/images/generations"

        print(f"[汇取云] 发送请求...")
        print(f"[汇取云] URL: {url}")
        print(f"[汇取云] Model: {model}, 图生图: {is_img2img}")

        # 汇取云比例转换：将用户选择的比例映射为汇取云的 size 值
        size_map = {
            "1:1": "1024x1024",
            "16:9": "1536x1024",
            "9:16": "1024x1536",
            "4:3": "1024x768",
            "3:4": "768x1024",
            "3:2": "1536x1024",
            "2:3": "1024x1536",
            "21:9": "1920x1080",
            "auto": "1024x1024",
        }
        if api_source == "汇取云":
            size_value = size_map.get(aspect_ratio, aspect_ratio)  # 优先用映射，没有则原样传递
        else:
            size_value = aspect_ratio

        # 构建 payload
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size_value,
            "response_format": "url"
        }

        # 图生图：添加 image 字段（base64 字符串数组）
        if is_img2img and image_base64_list:
            payload["image"] = image_base64_list
            print(f"[汇取云] 图生图添加 {len(image_base64_list)} 张图片")
            print(f"[汇取云] image字段长度: {len(image_base64_list[0]) if image_base64_list else 0}")

        print(f"[汇取云] size={size_value}, aspect_ratio={aspect_ratio}, is_img2img={is_img2img}")
        print(f"[汇取云] payload keys: {list(payload.keys())}")

        json_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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
            image_url = result.get("url") or result.get("image_url") or result.get("output_url", "")

        if not image_url:
            return None, f"未获取到图片URL: {result}"

        pbar.update_absolute(70)
        tensor = self._download_image(image_url)
        if tensor is None:
            return None, "图片下载失败"

        mode = "图生图" if is_img2img else "文生图"
        return tensor, f"成功 | 汇取云{mode} | {model} | {image_url[:50]}..."

    def _runninghub_submit(self, api_key, prompt, image_urls, aspect_ratio, resolution, is_img2img, api_source="Runninghub"):
        """提交 Runninghub 任务"""
        import urllib.request

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
                if is_img2img:
                    # 汇取云图生图：直接传 base64（不带 data:image/png;base64, 前缀）
                    image_base64_list = []
                    for img in valid_images:
                        image_base64 = self._image_to_base64(img)
                        # 去掉 data:image/png;base64, 前缀，汇取云只需要 base64 字符串
                        if "base64," in image_base64:
                            image_base64 = image_base64.split("base64,")[1]
                        image_base64_list.append(image_base64)
                    print(f"[ricksf节点] 已转换 {len(image_base64_list)} 张参考图为 base64")
                    image_tensor, result_info = self._huiqu_generate(api_key, model, prompt, aspect_ratio, image_base64_list, True, pbar)
                else:
                    image_tensor, result_info = self._huiqu_generate(api_key, model, prompt, aspect_ratio, [], False, pbar)

            elif api_source == "Runninghub":
                image_urls = []

                if is_img2img:
                    for img in valid_images:
                        image_base64 = self._image_to_base64(img)
                        image_urls.append(f"data:image/png;base64,{image_base64}")
                    print(f"[ricksf节点] 已转换 {len(image_urls)} 张参考图为 base64")

                # 提交任务
                task_id, error = self._runninghub_submit(api_key, prompt, image_urls, aspect_ratio, resolution, is_img2img, api_source)

                if error:
                    return (blank_tensor, f"提交失败: {error}", "", "")

                print(f"[Runninghub] 任务提交成功 taskId={task_id}")

                # 轮询（6分钟 = 360秒）
                pbar.update_absolute(30)
                max_wait = 360
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

                    pbar.update_absolute(min(70, 30 + int(waited * 0.1)))

            pbar.update_absolute(100)

            if image_tensor is not None:
                # 自动保存成功的 API Key 到本地
                if api_key_input.strip() and api_key_input.strip() != config.get(key_saved_name, ""):
                    config[key_saved_name] = api_key_input.strip()
                    save_config(config)

                # 更新历史
                if RicksfGPTImage2ComprehensiveNode._last_generated_image_urls:
                    RicksfGPTImage2ComprehensiveNode._last_generated_image_urls += "\n" + result_info
                else:
                    RicksfGPTImage2ComprehensiveNode._last_generated_image_urls = result_info

                history = RicksfGPTImage2ComprehensiveNode._last_generated_image_urls
                return (image_tensor, result_info, result_info.split("|")[-1].strip(), history)

            return (blank_tensor, result_info if result_info else "生成失败", "", "")

        except Exception as e:
            error_msg = f"执行失败: {str(e)}"
            print(f"[ricksf节点] {error_msg}")
            return (blank_tensor, error_msg, "", "")


NODE_CLASS_MAPPINGS = {
    "🙅GPT_image_2_综合@ricksf": RicksfGPTImage2ComprehensiveNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "🙅GPT_image_2_综合@ricksf": "🙅GPT_image_2_综合@ricksf",
}