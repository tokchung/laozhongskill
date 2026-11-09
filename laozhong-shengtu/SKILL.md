---
name: laozhong-shengtu
description: 老钟生图工具——把一句话出成图（豆包 Seedream / 火山方舟 Ark）。管住模型选择、尺寸、水印、落盘命名和报错定位。触发方式：「生图」「出张图」「画一张」「生成图片」「帮我做张图」「出几张挑一张」、/laozhong-shengtu。
user_invocable: true
version: "1.2.0"
---

# laozhong-生图：一句话 → 一张图

默认：**flash 模型 · 2K · 无水印 · 落到 `~/ai图片`**（用 `--out` 可改）。

## 零、先读这段（三条铁律）

1. **用脚本，不要手写 curl。** 中文 prompt 在 PowerShell 5.1 里会被 ANSI 弄乱（第五节坑 1），手搓必踩。
2. **key 不写进任何文档。** 脚本自动从 `ARK_API_KEY` 读（环境变量 → Windows 注册表 HKCU/HKLM）。**用前先 `setx ARK_API_KEY "你的key"`，重开终端生效。**
3. **报错先查错误码表，不要先怀疑 key。** 真正常见的是额度（429）和模型没开通（404 ModelNotOpen）。

## 一、一条命令搞定

```
python -X utf8 技能目录/laozhong-shengtu/ark_image.py "提示词" --name 主题名
```

长中文 prompt 走文件最稳（避开命令行编码）：

```powershell
# 先把提示词写成 UTF-8 文件（用 write 工具写，不要用 PowerShell 重定向——它写 UTF-16）
& $py -X utf8 ..\ark_image.py --prompt-file 提示词.txt --name 黑洞列车
```

### 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--model` | `flash` | `flash` / `5.0` / `4.5` / `pro`，也可直接写完整模型 ID |
| `--size` | `2K` | `2K`、`4K` 是档位；要**固定比例**就写死像素：`2560x1440`、`2048x2048`、`1728x2304` |
| `--name` | `图_时间戳` | 输出文件名主题（不带扩展名） |
| `--out` | `~/ai图片` | 输出目录 |
| `--n` | `1` | 出几张，自动加 `_v1 _v2` |
| `--watermark` | 关 | 打开右下角「AI生成」水印（发布合规场景才开） |
| `--open` | 关 | 出图后自动打开预览 |

出图后每张旁边会落一份 `req_<名字>.json`，**改一个词就能重跑**，不用重新拼 prompt。

## 二、模型矩阵（2026-11-02 实测，账户 2108247304）

| 别名 | 模型 ID | 状态 | 特点 |
|---|---|---|---|
| `flash` | `doubao-seedream-5-0-flash-260915` | ✅ 可用（默认） | 便宜快，视觉冲击类够用；第一次撞过「安全体验模式」额度 |
| `5.0` | `doubao-seedream-5-0-260128` | ✅ 可用（Retiring） | 电影质感、碎片/星尘细节更密 |
| `4.5` | `doubao-seedream-4-5-251128` | ✅ 可用（Retiring） | 空间透视、运动模糊、真实材质最强 |
| `pro` | `doubao-seedream-5-0-pro-260628` | ❌ 未开通 | 账户没激活，调了必 404 ModelNotOpen |

**选型口诀**：要冲击力 → `flash`；要电影感 → `5.0`；要"像拍的照片" → `4.5`。

⚠️ `-260128` / `-251128` 标了 Retiring，随时可能下线。真下线了报 `InvalidEndpointOrModel.NotFound`，换 `flash` 即可。
⚠️ `doubao-seedream-4-0-250828`、`doubao-seedream-3-0-t2i-250415` 这些旧 ID **已经不存在**，别从旧文档里抄。

## 三、API 规格

```
POST https://ark.cn-beijing.volces.com/api/v3/images/generations
Authorization: Bearer $ARK_API_KEY
Content-Type: application/json
```

```json
{
  "model": "doubao-seedream-5-0-flash-260915",
  "prompt": "……",
  "response_format": "url",
  "size": "2K",
  "stream": false,
  "watermark": true
}
```

- `response_format: url` → 返回的链接 **24 小时过期**，必须落盘（脚本已处理）
- `size: "2K"` 是档位不是像素。实测同一档位出现过 `2816x1584`、`2496x1664`、`3136x1344`——**要固定比例必须写 WxH**
- `watermark: true` → 右下角「AI生成」，发布到公众号/小红书合规场景才开

## 四、落盘与命名

```
~/ai图片/
  示例_主题_seedream-5.0-flash_2K.jpg
  同一主题_B.jpeg
  req_示例_主题_A.json     ← 请求体留档
```

- 一个主题多版本：`_v1 _v2 _定稿 _无文字版`
- 定稿后把 `req_*.json` 留着，事后想复刻一模一样的效果靠它

## 五、五个已经踩过的坑

**坑 1｜中文 prompt 一坏有两种死法：报错还算幸运，静默出废图才要命。**

**A. 报错型（能自己暴露）**：PowerShell 5.1 把 UTF-8 当 ANSI 读，`Get-Content payload.json -Raw` 读出来是「鏄熼檯绌胯秺」，`ConvertFrom-Json` 直接报 `应为":"或"}"`——你会以为 JSON 写错了，其实只是编码。GBK 双字节还会吃掉后面的 `"`，把 JSON 结构弄坏。

**B. 静默型（2026-11-02 实测，最坑）**：Git Bash / cmd 里 `curl -d '{...中文...}'` 内联传 body，**HTTP 200、不报错、url 正常返回、图也能下载**，但画面跟提示词**毫无关系**——当天连吃四张：OC 污染科普信息图／《疾速追杀》电影海报／公园城市规划图／商场建筑效果图。此时最容易误判成「模型不行」「账号被降级」「体验额度还在」。

**30 秒判断法**：同账号跑一句英文短 prompt（`a red apple on a blue wooden table, studio photo`）。英文正常、中文废 → 就是编码；两边都废才轮到怀疑模型或账号。

**正解**：中文一律走 `--prompt-file`。必须手搓 curl 时，把请求体写成 UTF-8 文件再 `curl --data-binary @请求体.json`，**永不 `-d` 内联中文**；PowerShell 里拼还要走 `[System.IO.File]::WriteAllBytes($p, [Text.Encoding]::UTF8.GetBytes($json))`。

**坑 2｜`size: "2K"` 给不了你要的比例。** 想要 16:9 写 `2560x1440`，想要竖版海报写 `1728x2304`。

**坑 3｜429 `SetLimitExceeded` 不是"调用太频繁"。** 是账户「安全体验模式」的免费额度到了，模型服务被暂停。去火山方舟控制台 → 开通管理 → 关闭或调高限额，重跑立刻就好。**注意：关掉额度只解决 429，不解决废图**——关掉后若图仍与提示词无关，那是坑 1B 的编码问题，别在额度上继续找。

**坑 4｜模型名一换版本就 404。** `ModelNotOpen` = 模型存在但没开通；`InvalidEndpointOrModel.NotFound` = ID 不存在。两者都是 404，含义不同，看 message 别只看状态码。

**坑 5｜提示词里的中文缩写模型不认。** `oc渲染` → 写 `Octane 渲染`；`抢视觉冲击力` 这类诉求要翻成画面语言（低机位、广角、逆光、碎片飞散）。负向需求**写成自然语言正句**：「画面中不要出现任何文字、字幕、标题、标志」。

## 六、提示词写法（实测管用）

六件事写全，比堆一百个形容词有用：

| 要素 | 例子 |
|---|---|
| 主体 | 快支离破碎的复古蒸汽列车 |
| 场景 | 从黑洞视界冲出，碎岩与星尘 |
| 镜头 | 低机位、夸张广角、微距 |
| 光 | 吸积盘暖橙背光，深蓝星场，单侧硬光 |
| 材质 | 锈蚀钢板、铆钉、烧穿的木板 |
| 氛围 | 末日、压迫、动感、超现实 |

- **镜头词 > 感觉词**：「低机位广角」比「电影感」管用十倍
- **对比色直接点名**：「暖橙压深蓝」「炭黑+陶土金」
- **静物要干净就明说**：「背景纯净、单一光源、纯净留白」

## 七、报错对照

| 状态 | code | 真因 | 动作 |
|---|---|---|---|
| 429 | `SetLimitExceeded` | 体验额度用尽/限流 | 控制台关「安全体验模式」，或换模型 |
| 404 | `ModelNotOpen` | 模型没开通 | 控制台开通，或换 `flash` |
| 404 | `InvalidEndpointOrModel.NotFound` | 模型 ID 不存在/无权限 | 核对模型矩阵 |
| 400 | `InvalidParameter`（parse JSON） | 请求体编码/转义坏了 | 走 `--prompt-file`，别内联拼 |
| **200** | **无错误码** | **出图正常但内容与提示词无关** | **提示词被编码弄坏**（坑 1B），不是模型/账号：换 `--prompt-file` 重跑，用英文短 prompt 对照 |
| 401/403 | `AuthenticationError` / `InvalidApiKey` | key 问题 | **先跑 api-self-check**，别直接判 key 过期 |

## 八、和其他 skill 的分工

- **laozhong-shengtu**（本 skill）：通用生图，一个 prompt 一张图
- **laozhong-shitu**：反向——读图、提取图中文字
- **concept-poster**：概念海报，固定 Anthropic 版式和 6 维语义解构
- **shejitu**：概念设计图，丝网印刷/拼贴风格
- 以上共用同一个 Ark 账户和 `ARK_API_KEY`；模型状态以本文件第二节为准

## 九、安全

- key 是敏感信息：**不进文档、不进记忆、不进日志**，脚本不打印 key
- 换 key：`setx ARK_API_KEY "新key"`，然后重开终端（脚本会自动读到）
- 客户图片、未发布物料出图后，别把 `req_*.json` 里的敏感 prompt 发到公开渠道
