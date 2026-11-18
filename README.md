# GRSlot-Toolkit

面向 AI Agent 的 Ricoh GR III 胶片数据准备与验证方法。仓库包含可执行检查工具、51 款有来源的胶片预设、菜单参考源码和验证契约。

**交付范围限于胶片数据、研究资料和源码。仓库不提供原厂或修改版固件、固件生成器、写卡或刷机工具。**

## 交给 Agent

把仓库地址发给 Agent，并说明你想使用哪些胶片、如何分配六槽、是否有自己的 LUT。例如：

> 请读取 GRSlot-Toolkit 的 SKILL.md。帮我校验本机提供的标准 GR III 原厂 2.10 文件，并根据我选的胶片准备本地配置及验证回执。

1. macOS 上使用 Python 3.9 或以上。从 Ricoh 官方渠道自行取得原厂更新包并解压，向 Agent 提供本机文件路径。
2. Agent 核对文件的完整 SHA-256、容器结构和参数基底。唯一支持的输入是标准 **GR III 原厂 2.10**。如果进一步评估机身兼容性，请在相机上另行核对机型和当前版本。版本高于 2.10 时停止，不尝试降级。
3. 选用随附胶片，或用 [DARKSLIDE GR](https://github.com/LiorMoment/darkslide-gr) 拟合自己的 LUT，再让 Agent 导入真实 profile，整理输出清单及校验回执。[Skill 入口](SKILL.md) · [Darkslide 输入契约](references/darkslide-import.md)

```bash
python3 scripts/check_firmware.py /absolute/path/to/official/fwdc239b.bin
python3 scripts/verify_assets.py
python3 -m unittest discover -s tests
```

## 使用范围与免责声明

GRSlot-Toolkit 是独立社区项目，与理光无隶属或授权关系。原厂固件应由使用者通过官方渠道自行取得，厂商名称及标识归各自权利人。用户应确认自己有权使用或分享所提供的 LUT、图标和其他素材。

使用修改固件可能导致相机无法开机、设置或照片丢失、设备损坏，也可能影响保修。若自行开展仓库范围之外的实验，应先核对机型和版本、备份数据，并确认适用的官方恢复条件。文件校验通过只表示输入符合本工具的支持范围。

项目按现状提供。无担保及责任限制以随附许可证和适用法律为准，依法不得排除或限制的责任仍适用。[使用前提与风险](references/usage-and-risk.md) · [许可证](LICENSE)

## 致谢

- 感谢 **Andrea Volpato** 开源 Spektrafilm，随附 16 款相机拟合预设的数据适用 CC BY-SA 4.0。[Spektrafilm](https://github.com/andreavolpato/spektrafilm)
- 感谢 **Jan Lohse** 开源 Spectral Film LUT，随附 35 款相机拟合预设的数据适用 MIT。[Spectral Film LUT](https://github.com/JanLohse/spectral_film_lut)
- 感谢 **LiorMoment** 创建 DARKSLIDE GR 并提供 LUT 拟合能力，也感谢 **Ady0402** 和桌面版贡献者。[DARKSLIDE GR](https://github.com/LiorMoment/darkslide-gr) · [LiorMoment](https://github.com/LiorMoment) · [Ady0402](https://github.com/Ady0402)

程序与 skill 文档按 **GPL-2.0-only** 提供。第三方数据、字体和其他材料保留各自的许可。逐款署名及文件指纹记录在胶片清单。[来源说明](SOURCES.md) · [第三方声明](THIRD_PARTY_NOTICES.md) · [胶片清单](assets/library.json)
