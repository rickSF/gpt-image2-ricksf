# gpt-image2-ricksf

GPT Image 2 生图节点插件，支持**汇取云**和**Runninghub**两大 API 生图渠道。

作者：@ricksf

---

## 📦 包含节点

### 1. 汇取云生图 🏞️

使用汇取云 API 生成图片。

| 参数 | 说明 |
|------|------|
| API密钥 | 汇取云 API Key |
| 提示词 | 生成图片的描述 |
| 模型 | gpt-image-2（¥0.068/次）/ gpt-image-2-FL（¥0.045/次）/ gpt-image-2「备用」（¥0.085/次） |
| 输出格式 | url / b64_json |

**API 配置：**
- 地址：`https://api.bjhuiqu.net/v1/images/generations`
- 仅支持文生图

---

### 2. Runninghub 文生图 🌅

使用 Runninghub API 从文字生成图片。

| 参数 | 说明 |
|------|------|
| API密钥 | Runninghub API Key |
| 提示词 | 生成图片的描述 |
| 比例 | 1:1 / 16:9 / 9:16 / 4:3 / 3:4 / 21:9 |
| 分辨率 | 1k / 2k |

**API 配置：**
- 地址：`https://www.runninghub.cn/openapi/v2/rhart-image-g-2/text-to-image`
- 价格：¥0.1/次

---

### 3. Runninghub 图生图 🖼️

使用 Runninghub API 基于参考图片生成新图片。

| 参数 | 说明 |
|------|------|
| API密钥 | Runninghub API Key |
| 提示词 | 生成图片的描述 |
| 参考图 | 输入的参考图片 |
| 比例 | 1:1 / 16:9 / 9:16 / 4:3 / 3:4 / 21:9 |
| 分辨率 | 1k / 2k |

**API 配置：**
- 地址：`https://www.runninghub.cn/openapi/v2/rhart-image-g-2/image-to-image`
- 价格：¥0.1/次

---

### 4. GPT Image 2 综合版

支持在单个节点中选择 API 渠道和模式。

- 支持：汇取云 / Runninghub
- Runninghub 自动判断：有参考图→图生图，无参考图→文生图

---

### 5. GPT Image 2 官方稳定版

功能完整的稳定版本，支持所有生图模式。

- 汇取云：仅文生图
- Runninghub：文生图 / 图生图

---

## 🔧 安装方法

### 方式一：ComfyUI Manager

在 ComfyUI Manager 中搜索 **"gpt-image2-ricksf"** 并安装。

### 方式二：手动安装

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/T8mars/gpt-image2-ricksf.git
```

---

## 💰 价格对比

| API | 模型/接口 | 价格 |
|-----|----------|------|
| 汇取云 | gpt-image-2 | ¥0.068/次 |
| 汇取云 | gpt-image-2-FL | ¥0.045/次 |
| 汇取云 | gpt-image-2「备用」 | ¥0.085/次 |
| Runninghub | rhart-image-g-2/text-to-image | ¥0.1/次 |
| Runninghub | rhart-image-g-2/image-to-image | ¥0.1/次 |

---

## 📝 使用示例

1. 选择 API 渠道（汇取云/Runninghub）
2. 填写 API 密钥
3. 输入提示词
4. 选择比例和分辨率
5. 执行节点生成图片

---

## 🙏 致谢

- 汇取云 API：`https://api.bjhuiqu.net`
- Runninghub API：`https://www.runninghub.cn`