---
name: ricoh-gr3-film-firmware
description: 用标准 GR III 原厂 2.10 和随附开源预设在本机生成 GRSlot 固件候选，也可准备和验证本地胶片数据。
metadata:
  license: GPL-2.0-only
  compatibility: macOS、Python 3.9+；构建需要 Apple Clang 和 Unicorn 2.1.4，数据准备使用标准库。
---

# GRSlot 通用分发准备

## 先读能力状态

读取 [capabilities.json](assets/capabilities.json)。当 `offline_build_checks` 为 true 时可以运行离线构建检查。当 `firmware_candidate_output` 为 true 时，检查通过后保存离线候选。当前 `firmware_container_output` 为 false，请勿改名、写卡或刷机。

首次使用或用户问能否装进相机时，先走 [AGENTS.md](AGENTS.md) 的新手流程。用随附的开源胶片预设跑通一次离线构建检查，再处理自定义胶片。Studio Lite 的配置和保存无需原厂输入，离线构建检查需要原厂输入。

唯一支持标准 GR III 原厂 2.10，完整 SHA-256 为

```text
d6a3c9c288d784080e7b283222ecdd8752adfeed6faa36dab44f73115354bfd4
```

在 skill 根目录运行，输入输出均用绝对路径。

```bash
python3 scripts/check_firmware.py /absolute/official/fwdc239b.bin
python3 scripts/verify_assets.py
```

校验失败即停止使用该输入。若评估相机兼容性，请使用者另行确认机身为标准 GR III 并运行原厂 2.10。高于 2.10 时停止，不尝试降级。参见 [使用前提与风险](references/usage-and-risk.md)。

## 按任务读取和执行

### 构建本机固件候选

首次用随附胶片和默认六槽，在仓库根目录执行：

```bash
python3 -B studio-lite/build_firmware.py --bundled --firmware "/absolute/fwdc239b.bin" --output "/absolute/new-output"
```

已有随附胶片的 Studio Lite 项目时，用 `--project "/absolute/project.json"` 替换 `--bundled`。输出目录必须尚不存在，父目录需已存在。回执 `PASS_OFFLINE_ARM_CONTAINER` 表示 `GRSlot.NOT-INSTALLABLE` 已生成并通过电脑检查。实机结果见回执中的 `camera_status`。

### 读取 Studio Lite 项目

用户可用 Studio Lite 配置胶片、Golden 六槽、名称、分类、图标与备注。拿到保存的 `project.json` 和原厂 BIN（或其文件夹）后，在仓库根目录执行：

```bash
python3 -B studio-lite/check_project.py --project /absolute/project.json --firmware /absolute/official
```

使用自定义胶片库时，加 `--library /absolute/prepared-library/library.json`，必须与 Studio 保存项目时的库匹配。以回执中的 `selected`、`slots` 和 `project_sha256` 汇报本次配置。验证入口是只读的，`PASS_STUDIO_PROJECT_ONLY` 表示项目、胶片资产与原厂输入均通过准备阶段校验。当前产物为数据和回执。完整流程见 [使用说明](docs/guide.md)。

### 配置随附胶片

用 [胶片清单](assets/library.json) 的 UID 选择预设，按 Slot 1 到 Slot 6 顺序指定默认胶片。每个槽位须指向已选 UID。这里创建的是本地数据项目。

```bash
python3 scripts/import_darkslide.py \
  --firmware /absolute/official/fwdc239b.bin \
  --select 5 8 9 \
  --slots 5 8 9 5 8 9 \
  --output /absolute/new-grslot-project
python3 scripts/verify_assets.py /absolute/new-grslot-project
```

成品目录的根 `library.json` 是唯一配置清单。`films` 保留可用目录，`selected` 指定本次选用的 UID，`defaults` 按顺序对应六槽。回执包含清单 SHA-256。本地目录可用 `--previous` 继续配置。

### 拟合并导入胶片

收到原始 CUBE 时，先在 [DARKSLIDE GR](https://github.com/LiorMoment/darkslide-gr) 核对色彩空间，完成拟合和原厂范围检查。导出 CUBE 用于外观预览，准备脚本读取真实项目与 profile。

读取 [Darkslide 输入契约](references/darkslide-import.md)。从真实项目读取 `profile`，核对源 CUBE 身份、原厂 SHA、拟合器、基础模型及指定基底 SHA，并检查 Darkslide 声明的 factory envelope 结果。

```bash
python3 scripts/import_darkslide.py \
  --project /absolute/darkslide-project \
  --firmware /absolute/official/fwdc239b.bin \
  --id user_lut_0123456789ab \
  --output /absolute/new-grslot-project
```

`--id` 可重复。增量导入用 `--previous /absolute/previous-project`，输出选择新的同级目录。内容相同的 profile 复用 UID，JSON 键顺序不改变身份。新增 UID 追加，退役 UID 保留。省略选片参数时保留上一次选择，并加入本次导入的 UID。名称覆盖用单条导入的 `--name`，作者用 `--author`，未知作者保留 Unknown。用户数据留在本地项目。

缺少真实 profile 时先完成 Darkslide 拟合。外观 CUBE 无法替代相机参数。M2 沿用现有精确 CSP 编码，完整保留 RGB 曲线和 M1。

### 修改菜单源码

读取 [菜单自定义](references/menu-customization.md)。工作副本修改 `source/p5/` 和相应资源、注册表、消费者及测试。构建器在临时目录根据本次胶片库和槽位生成三个头文件。

保全六槽独立九项参数与 Grain。Install、Restore Current、Restore All 只改 Assignment。保全完整导航、确认页、原生标题图标、活动面板检查和 Fn/ISO/ADJ 隔离。Change Film 直接进入六槽，品牌多版本采用品牌 → 胶片 → 版本。Favorites 为构建期配置。显示身份按当前 Slot Assignment 处理。

### 准备分发

以 [library.json](assets/library.json) 为准，当前 59 款，包括 16 款 Spektrafilm、35 款 Spectral Film LUT 和 8 款补充预设。默认 Studio UID 为 39、40、88、41、5、86。

分发按清单的许可逐款选取文件。公开候选从本次用户原厂输入构建。来源与许可见 [SOURCES.md](SOURCES.md) 和 [第三方声明](THIRD_PARTY_NOTICES.md)。

## 验证与交付

按 [验证要求](references/validation.md) 检查实际改动。构建成功时给出固件候选及回执路径和实际验证范围。Windows/Linux 尚待验证。
