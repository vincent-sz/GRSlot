# 当前构建状态

## 公开版固件候选构建

`studio-lite/build_firmware.py` 构建和校验容器，把 `fwdc239b.candidate.bin` 写入磁盘并读回核对 SHA-256。输出目录另含 `SHA256.txt`、`studio-project.json` 和 `verification.json`。`PASS_DESKTOP_ARM_CONTAINER` 代表本次桌面检查通过。`BLOCKED_PENDING_RELEASE_VALIDATION` 表示升级文件仍未放行。

离线检查覆盖六槽 DNG 影像控制标记的写入和重新读取、回放槽位和图标、按照片记录显示 Grain，以及经原厂按键入口触发的菜单导航、安装与恢复。绘制回归检查原生绘制回调发出的命令，实机画面和真实照片流程仍待确认。完整验收见 [验证要求](validation.md)。

## 撤回的 WorkBuddy 候选

完整 SHA-256 为 `b59f6d3a8df672e2acedec6a54fa5817b7ee0cc141af9d1b8487be9c460a099f` 的文件已撤回。审查在该文件中复现了 RAW 对象内存分配失败后的空地址访问。请勿用于相机更新。

## 最新私人实机参考

FilmInfo 20261118 已通过用户实机验收，对应 SHA-256 `7bbd37207457487b3cb73a47173d6b9b87d7e42984c0765ef60dc525b0d7e54a`。胶片资料页仅显示胶片名、指定署名和已有色温备注。该实机回执用于参考，分发版的源码同步点仍见下节。

## 分发版菜单源码同步点

`GRSlot_Vincent_Work_StdDefault_20261117/firmware/fwdc239b.bin`

SHA-256 为 `a211bbffa63c2151dfba10c64454c9e4ae04e91eedeb55e7dfdd056abcb42672`，Vincent 于 2026-11-17 确认 Slot 3 默认 HNCS Std 的 83 款版本实机 PASS。本包菜单主体保留已同步的品牌分组逻辑，私人扩库及六版本容量在专用本地工作流维护，带品牌—胶片—版本导航及 FAMILIES 绘制修复。通用可移植构建能力继续由 capabilities.json 表示。
