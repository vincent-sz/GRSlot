# GRSlot 使用说明

GRSlot 让 AI Agent 为标准 **Ricoh GR III** 准备一份胶片配置。可以从仓库的 51 款滤镜里选，也可以加入自己用 DARKSLIDE GR 拟合的 LUT。最终交付是本地数据目录、胶片清单和校验回执。

## 1. 准备原厂文件

在 macOS 上准备 Python 3.9 或以上。通过 Ricoh 官方渠道自行取得**标准 GR III 原厂 2.10** 更新包并解压，把 `fwdc239b.bin` 的本机路径交给 Agent。工具以完整 SHA-256、容器结构和参数基底识别这份文件。同名 BIN、其他机型和更高版本文件均不能代替。

如果还要检查与手头相机的对应关系，请在机身上另行确认机型和当前版本。机身版本高于 2.10 时停止，流程不支持降级。[使用前提与风险](../references/usage-and-risk.md)

## 2. 选胶片并设置六槽

把本仓库地址交给 Agent，再给它原厂 BIN 路径、想选的胶片和六槽顺序。显示名相近时，以[胶片清单](../assets/library.json)中的 UID 区分版本。

> 请按 GRSlot 的 SKILL.md 校验我本机的原厂 2.10 文件。选 Vision3 5207（UID 5）、Gold 200（UID 12）、Portra 400（UID 14）、Pro 400H（UID 9）、Ultramax 400（UID 18）和 Ektar100（UID 11），按这个顺序分配槽位 1 到 6。把配置输出到仓库外的新目录，验证后告诉我路径。

在仓库根目录，Agent 可以直接执行同样的步骤：

```bash
python3 scripts/import_darkslide.py \
  --firmware /absolute/official/fwdc239b.bin \
  --select 5 12 14 9 18 11 \
  --slots 5 12 14 9 18 11 \
  --output /absolute/grslot-project

python3 scripts/verify_assets.py /absolute/grslot-project
```

`--select` 是本次选用的胶片，`--slots` 必须有六个 UID，且每个都在选用清单中。同一款可以分到多个槽位。

## 3. 可选：加入自己的 LUT

在 DARKSLIDE GR 中使用同一份原厂文件建项目。导入你有权使用的 `.cube`，核对色彩空间，完成拟合并确认 Darkslide 报告的原厂范围检查通过。接着把**项目目录**和要导入的 LUT 条目交给 Agent。它会读取真实 profile。Darkslide 导出的相机预览 CUBE 用于预览外观。

从上一步的配置追加一款：

```bash
python3 scripts/import_darkslide.py \
  --project /absolute/darkslide-project \
  --firmware /absolute/official/fwdc239b.bin \
  --id user_lut_0123456789ab \
  --previous /absolute/grslot-project \
  --output /absolute/grslot-project-next
```

`--id` 使用项目里的真实 ID。追加后看回执里的 `imported_uids`。默认保留上一次的六槽，把所导入的胶片加入选用清单。如果希望换进某个槽位，再用新目录作为 `--previous` 配置一份六槽。[Darkslide 输入契约](../references/darkslide-import.md)

## 4. 检查交付物

| 文件 | 看什么 |
| --- | --- |
| `library.json` | `films` 是可用目录，`selected` 是本次选片，`defaults` 按顺序对应槽位 1 到 6。 |
| `RECEIPT.json` | 核对输入固件版本、选用 UID、六槽映射和清单 SHA-256。导入自有 LUT 时，Darkslide 的范围声明单独记录。 |
| `assets/` | 胶片 profile、原生参数和随附图标。校验器会核对必需文件以及编码。 |

配置目录用于检查、记录和继续调整。本仓库的交付到此为止，没有生成或安装相机固件的入口。

## 参考：相机菜单怎么走

以下说明对应 [README 中的菜单预览](../README.md#在相机上是什么样)，供了解已有 GRSlot 版本的行为：

1. 在 **GRSlot 菜单**里先选六个 Golden 槽位中的一个，再选 **胶片库 / Film Library**。
2. 进入品牌分类，选胶片。有多个拟合版本的胶片会继续显示版本列表。
3. 在胶片操作页选 **胶片资料 / Film Info** 可看名称、可用署名和备注。选 **装入槽位 / Install to Slot** 会出现确认页，确认后才改变已有版本中该槽的胶片分配。
