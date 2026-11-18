# 菜单自定义

用户已批准整套成功版 UI 纳入 skill，并允许其他使用者自行修改。

## 源码与资源

- `source/p5/menu.c` 为当前分发包的菜单主体，12 个可达页面，保留枚举编号 MAIN。
- `source/p5/core.c` 为既有 Assignment journal 逻辑。
- `source/p5/p4a.h`、`native_font.inc`、`native_frame.inc` 为现有 ABI 和绘制适配。
- `assets/icons/films/` 提供 51 款胶片的 40×40 RGBA，首批 12 款另有 PNG、描边 SVG 和布局数据。
- `assets/icons/ui/` 提供菜单图标 SVG 和原始图标数据。

三个头文件 `film_bank.h`、`library_data.h`、`families.h` 必须由经过验证的平台构建生成。本开发包用明确的编译错误保护这一缺口，防止未经绑定的地址进入候选。

## 可修改内容

菜单文案、胶片显示名称、图标、分类、分类顺序、胶片排列、收藏构建配置、页面布局、焦点样式及按键导航均属于允许的自定义范围。修改以用户请求为边界，优先复用现有绘制和导航实现。

当前成功版导航为 SLOTS → ENTRY → CATEGORIES → FAMILIES（分组品牌）→ GRID（多版本）→ ACTION；单版本从 FAMILIES 直达 ACTION，其他大类从 CATEGORIES 进入 GRID。安装、详情和恢复默认拥有对应确认或返回路径。ACTION 包含 Install to Slot、Favorites: Build Config、Film Info、Back。收藏按构建配置生效。

固定六槽和颜色链身份属于当前平台契约。修改菜单页数不等于扩大 Image Control 槽位数量。

## 联动验证

精简或新增胶片时，同时检查分类计数、空分类、翻页、名称和图标指针、film order、默认映射、Restore Current 和 Restore All。导航修改覆盖首尾循环、上下左右、拨轮、确认及逐级返回。

原生 Select 视图复用会保留绘制回调。`grs_draw` 绘制前须通过活动面板检查（当前平台 `0x540c5a58`，GRSlot 面板 `0x02000141`）。复用平台时核对该绑定，回归覆盖 Fn、感光度、ADJ 等原生菜单、原厂 underlay 和 GRSlot 返回。

文字和布局需检查 LCD 宽度、分页及焦点范围。新资源不得覆盖原厂资源。保持参数、Grain、持久化和 RAW/Playback 的实际消费者关系。

当前包可交付源码修改和参数准备，完整固件输出受平台重建缺口约束。

新视图须同时接入按键与绘制。BrandFilm 初版因 FAMILIES 漏进绘制条件而出现空白，Fix1 已补齐。验证必须确认原生文字、卡片、焦点及实际 paint callback，单色背景变化会造成漏检。
