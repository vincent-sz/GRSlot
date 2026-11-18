# 来源锁与采用范围

## 功能基线

`GRSlot_Vincent_Work_ButtonMenuFix_20261115`，固件 SHA-256 `32b6c4ffe15acd69f9b69c090ebbf6e04bb6fabc31d46f1788daf91cfa578d0d`。

菜单与 Assignment 源码继承 2026-11-04 KeepImageControl，菜单绘制同步 2026-11-15 ButtonMenuFix 的活动面板检查。作者于 2026-11-15 确认按钮设定菜单修复成功。原始 `film_bank.h` 和 `library_data.h` 含排除条目，未收入本仓库。

## Native 编码器

Fraction CSP 变换与实际整数系数核验来自既有 `GRSlot_V3Native_P2_20261101-1601/PATCH_SOURCE/encode.py`。本次抽出纯编码逻辑，增加输入类型和溢出检查，去除历史 RTOS 路径依赖。对照现有 12 款编码文件逐字节检查。

## 原版 Darkslide GR

上游为 [LiorMoment/darkslide-gr](https://github.com/LiorMoment/darkslide-gr)，固定提交 `4d7ad1a40da10572aba48177c946785de3087dc4`。

- `scripts/cube_reader.py` 保留该源的 `darkslide/film_luts.py` 纯 CUBE 解析器与异常逻辑。
- 原厂项目及拟合来源检查依据 `darkslide/store.py` 的 `film_lut_profiles`。
- profile 矩阵、曲线、白保持和 ARM 累加边界依据 `darkslide/film_profiles.py`、`film_numeric.py`。
- GPL-2.0-only 原文随附。程序代码许可与胶片数据许可分别列明。

## 胶片数据

11 款已拟合数据来自 `GRSlot_V3_SPK11_Resource_Prep_20261103/parameters/`，与成功版实际使用的参数指纹一致。Vision3 5207 来自成功版对应的 Native P3 数据。每款的 profile、来源 SHA、文件 SHA 和历史 UID 在 `assets/library.json` 记录。

原始数据作者 Andrea Volpato，项目为 [Spektrafilm](https://github.com/andreavolpato/spektrafilm)。Darkslide 的导出、白点调整及拟合由 LiorMoment 进行。数据及其直接派生结果按 CC BY-SA 4.0，许可和原附加说明完整保留。

公开源码包包含 16 款 Spektrafilm 和 35 款 Spectral Film LUT 的相机拟合预设。Spektrafilm 的 4 款早期拟合以 `(Original Fit)` 区分同名版本。Spectral Film LUT 由 Jan Lohse 开发，上游 MIT 许可随附。35 款实际经 Alcedo 的 ACEScc CUBE 导出，再转换为显示参考 sRGB、由 Darkslide 拟合。逐款导出标识、设置和阶段哈希见 [派生记录](CHANGELOG.txt)。现有档案未锁定 Alcedo 导出包发布版本和 Spectral 生成器提交，须以实际导出包授权材料完成公开复核。[Spectral Film LUT 上游仓库](https://github.com/JanLohse/spectral_film_lut)

## 图标

来源为 `GRSlot_V3_AllIcons_SourceHanSans_Bold_Fix1_20261103` 中本次准入胶片及 UI 图标。首批 12 款保留描边 SVG 和布局说明，51 款均附 40×40 RGBA。字体为 Adobe Source Han Sans，SIL OFL 1.1 许可随附。本次删除图标 SVG 标题中的显示后缀，保留原有像素。

## 容器工具

`scripts/container_codec.py` 采用成功构建链中已使用的 `GRSlot_V3_P4B_Fix2_20261102-0441/PATCH_SOURCE/support/firmware.py` 的解码与验证部分。未带入旧槽位替换生成入口及其 HNCS 数据资产。

## 上游 MIT 来源

既有固件研究中的部分 ARM 模式源于 [idontknownihil/gr3-film-mods](https://github.com/idontknownihil/gr3-film-mods)，固定提交 `04d5d5dd6e85d80089c6200bd0f0de5fff2d658f`。沿用原有 MIT 版权许可记录。完整平台框架的逐模块来源还需要补齐，目前不随本包分发历史底座或 append 二进制。
