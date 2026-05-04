# gpt-image2-ricksf

GPT Image 2 生图节点插件（综合版），支持**汇取云**和**Runninghub**两大 API 生图渠道。

作者：@ricksf

---

## 📦 节点说明

### 🙅GPT_image_2_综合@ricksf

在单个节点中支持所有功能：

- **API渠道**：汇取云 / Runninghub
- **模式**：有参考图自动切换图生图，无参考图自动切换文生图
- **参考图**：最多支持4张参考图

---

## 💰 价格

| API | 模式 | 价格 |
|-----|------|------|
| 汇取云 | 文生图/图生图 | ¥0.068/次 |
| Runninghub | 文生图/图生图 | ¥0.1/次 |

---

## 🔧 安装方法

### 方式一：ComfyUI Manager

在 ComfyUI Manager 中搜索 **"gpt-image2-ricksf"** 并安装。

### 方式二：手动安装

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/rickSF/gpt-image2-ricksf.git
```

---

## ⚙️ API Key 配置

节点支持两种 API Key 配置方式：

### 方式一：config.json 配置（推荐）

在节点目录下创建或编辑 `config.json`：

```json
{
  "huiqu_api_key": "你的汇取云API密钥",
  "runninghub_api_key": "你的Runninghub API密钥",
  "备注": "API密钥配置，优先读取此文件，没有则读取节点输入。成功运行一次后会根据节点输入自动更新对应渠道的Key。"
}
```

### 方式二：节点输入

直接在节点输入框填写 API 密钥。成功后会自动保存到 `config.json`。

---

## 📐 参数说明

| 参数 | 说明 | 备注 |
|------|------|------|
| API渠道 | 选择生图渠道 | 汇取云 / Runninghub |
| API密钥 | API Key | 支持 config.json 读取 |
| 提示词 | 图片生成描述 | |
| 参考图1-4 | 参考图片（可选） | 有参考图自动切换图生图 |
| 比例 | 输出图片比例 | auto / 1:1 / 16:9 / 9:16 / 4:3 / 3:4 / 3:2 / 2:3 / 21:9 |
| 分辨率 | 输出清晰度 | 1k / 2k / 4k |
| 模型 | 选择模型 | 仅汇取云可用 |

---

## 🔌 API 端点

### 汇取云

- **地址**：`https://api.bjhuiqu.net/v1/images/generations`
- **认证**：`Authorization: Bearer <API_KEY>`
- **Content-Type**：`application/json`
- **图生图**：图片作为 base64 字符串数组通过 `image` 字段传递

### Runninghub

- **文生图**：`POST https://www.runninghub.cn/openapi/v2/rhart-image-g-2/text-to-image`
- **图生图**：`POST https://www.runninghub.cn/openapi/v2/rhart-image-g-2/image-to-image`
- **查询**：`POST https://www.runninghub.cn/openapi/v2/query`
- **认证**：`Authorization: Bearer <API_KEY>`
- **图生图**：图片作为 base64 data URI 数组通过 `imageUrls` 字段传递

---

## 📝 使用示例

1. 配置 API Key（通过 config.json 或节点输入）
2. 选择 API 渠道
3. 输入提示词
4. 选择比例和分辨率
5. 有参考图则自动进行图生图，无参考图则进行文生图

---

## 🙏 致谢

- 汇取云 API：`https://api.bjhuiqu.net`
- Runninghub API：`https://www.runninghub.cn`