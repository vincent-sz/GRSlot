# 原版 Darkslide 输入契约

## 用户操作

在原版 Darkslide 中以指定标准 GR III 2.10 原厂固件创建项目，导入用户有权使用的 3D CUBE，并完成胶片拟合和原厂范围检查。向 agent 提供项目文件夹。

macOS 默认位置为 `~/Library/Application Support/Darkslide/projects/<project_id>/`。用户配置 `DARKSLIDE_DATA` 时以该目录为准。只读取用户指定项目，避免无关项目扫描。

```text
project.json
film_luts.json
luts/
  user_lut_<12 hex>.cube
```

原版固定版本中，GUI 下载的 `.camera.cube` 用作相机模型预览。真实拟合数据在 `film_luts.json` 对应条目的 `profile` 中。用户仅提供 CUBE 时，先取得完成拟合后的项目数据。

## 严格检查

- `project.json.input_sha256` 必须匹配指定原厂 SHA。
- 条目 ID 由原始 CUBE SHA 的前 12 位生成，条目 SHA 和 profile 来源 SHA 均须对应同一原件。
- profile 为 schema 1、GR III、2.10，M1 为 3×3 Q13，曲线为 3×256 U14，post 为 3×3 Q512。
- 拟合器为 `darkslide-film-fit-v2`，基础模型限定已验证的 `gr3-210-upstream-neutral-stubbed-v2`。
- 使用 `four_curve_v1`，sRGB 输入，target EV 0，mid_index 7.8，并保留基础数据 SHA。
- `fit.envelope.checked` 为 true，模型为 `gr3-210-stored-look-and-curve-bounds-v1`，violations 为空。
- JSON 重复字段、NaN/Infinity、整数中的布尔值、溢出矩阵及不支持的输入均拒绝。

其他 Darkslide 基础模型须先单独验证。该限制用于锁定当前 Native 消费前提。

## Native 编码

M1 原样写为 18 B，全部 RGB 曲线原样写为 1536 B。M2 使用已有 V3 P2 的 Fraction 精确坐标变换，转换为 36 B 原生 CSP 系数，并核对最终整数系数与 Darkslide 输出一致。原厂输入中的固定 B 矩阵由原厂校验工具读取核实。

编码结果是胶片数据准备，不代表完整固件、实机颜色一致性或实机验收。

## 元数据与本地性

名称优先采用 Darkslide 条目名称。当前成功版菜单适用的短名范围为 ASCII 1–32 字符，需要其他显示名称时先征询用户并通过 `--name` 显式提供。`--author` 由用户或可信来源提供，默认 Unknown。

新胶片图标由用户选择模板或提供自有图像，当前导入结果的 `icon` 留空，交付固件前必须完成这一项。禁止将空值解释为已生成图标。

导入输出放在仓库外的新目录。再次导入以 `--previous` 指向旧项目并生成新的同级目录。相同 profile 不重复分配 UID，失败检查在创建输出前完成。原项目、用户 CUBE 和旧输出均受保护。

用户数据及其派生参数按用户授权在本地处理。自动 Git 提交、上传或重新赋予共享数据许可不属于导入动作。
