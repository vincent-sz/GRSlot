# GRSlot 公开版的 Agent 操作指南

先读取本仓库的 `README.md` 和 `assets/capabilities.json`。按用户使用的语言回答。首次使用时，先用用户能照做的步骤回应，脚本和技术细节按需提供。

## 用户说「请帮我把 GRSlot 装到固件里」

读 `assets/capabilities.json`。当 `firmware_candidate_output` 为 true 且用户已给原厂文件时，用仓库随附的公开预设构建离线候选。当前 `firmware_container_output` 为 false，禁止改名、写卡或交给相机更新。

1. 在仓库根目录检查 `xcrun --find clang`，并用准备运行构建的 Python 确认能 `import unicorn`。缺依赖时告诉用户具体缺项和安装方法。
2. 用上一步确认可导入 Unicorn 的同一个 Python 解释器运行 `python3 -B studio-lite/build_firmware.py --bundled --firmware "用户提供的原厂 BIN 路径" --output "仓库外的新本机输出目录"`。如果确认的是虚拟环境或其他 Python 路径，就在命令里用该路径替换 `python3`。已有 Studio Lite 项目时，用 `--project "用户提供的 JSON 路径"` 替换 `--bundled`。
3. 读取新目录里的 `verification.json`。看到 `PASS_OFFLINE_ARM_CONTAINER` 和 `firmware_generated: true` 后，确认 `firmware_path` 指向实际存在的 `GRSlot.NOT-INSTALLABLE`，再把文件路径、回执路径和实机状态告诉用户。原厂文件只在本机读取。

## 用户说「先试一下」或请你打开 Studio Lite

1. 能在用户的 macOS 电脑上读取仓库并执行命令时，检查 `python3 --version`，需要 3.9 或以上。从仓库根目录运行 `python3 -B studio-lite/app.py --port 0`，由系统分配空闲端口。保留服务进程，将终端实际显示的本机网址告诉用户。如果启动失败，说明具体错误。Windows 和 Linux 尚待验证。
2. 当前聊天无法在用户电脑上运行命令时，直接给出手动入口。请用户在 macOS 的访达里打开本机 GRSlot 文件夹，进入 `studio-lite`，双击 `启动 Studio.command`。如果启动失败，让用户贴出错误文字。若端口被占用，再引导用户用上一步的命令。仅提供手动步骤时，用「请打开」，实际成功启动后再说「已打开」。
3. 浏览器打开后，先载入随仓库附带的开源胶片库。请用户勾选想用的胶片，在右侧把 Slot 1 换成一款已勾选的胶片，再点右上角「保存项目」。先用随附预设跑通选片、分配和保存。用户想做完整桌面校验时，继续用这份配置校验。走完这条流程后，再引导用户导入自己的预设。

## 用户明确要校验已保存的配置

按 `SKILL.md` 的「读取 Studio Lite 项目」操作。请用户提供 Studio 的「复制路径」显示的项目 JSON，以及从理光官方渠道取得的标准 GR III 原厂 2.10 BIN 或它所在的文件夹。使用自定义胶片库时，还需提供保存时使用的 `library.json`。完整校验通过后，按 Slot 1 到 Slot 6 列出胶片名，并把 `PASS_STUDIO_PROJECT_ONLY` 解释为「项目、胶片文件和原厂输入已通过桌面检查」。
