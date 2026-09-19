# Folder Skin · 文件夹换肤（可更换全局默认文件夹图标）

#### **图库展示（在generated_icons文件夹下）：**

![屏幕截图 2026-09-19 225706](folder_skin_tool\images\屏幕截图 2026-09-19 225706.png)

#### **character和file图标在asset文件夹下：**

<img src="folder_skin_tool\images\屏幕截图 2026-09-19 225904.png" alt="屏幕截图 2026-09-19 225904" style="zoom:50%;" />

<img src="folder_skin_tool\images\屏幕截图 2026-09-19 225847.png" alt="屏幕截图 2026-09-19 225847" style="zoom:50%;" />

"D:\Desktop\interesting\folder_skin_tool\folder_skin_tool\images"

#### **效果展示：**

<img src="folder_skin_tool\images\屏幕截图 2026-09-19 224240.png" alt="屏幕截图 2026-09-19 224240" style="zoom:50%;" /><img src="folder_skin_tool\images\屏幕截图 2026-09-19 224643.png" alt="屏幕截图 2026-09-19 224643" style="zoom: 67%;" />



第一次使用请阅读同目录的 **新手使用指南.md**，其中包含操作步骤、不注销时的刷新办法，以及两种换肤方式的恢复说明。

双击 **Start.cmd** 启动。使用现有的 `E:\Anaconda\envs\comp5310\python.exe`，无需安装新环境。

1. 选择本地普通文件夹。
2. 选择透明 asset/character/下PNG。
3. 可在角色选项下方选择「文件夹皮肤 PNG（在）asset/file/」，替换整个纯色文件夹外观。
4. 调整角色大小和上下位置；右侧可独立调整皮肤 PNG 的大小和上下位置。颜色仅影响纯色模式。
5. 点击「应用皮肤」直接换肤，不会自动导出 PNG/ICO 副本。需要保存成品时，点击「手动保存 PNG + ICO」，选择位置和文件名；取消对话框不会保存。
6. 随时点击「恢复所选文件夹」或「恢复全部已换肤文件夹」。

## 让角色进入文件夹

#### **参数建议：**

<img src="folder_skin_tool\images\屏幕截图 2026-09-19 224944.png" alt="屏幕截图 2026-09-19 224944" style="zoom:50%;" /><img src="folder_skin_tool\images\屏幕截图 2026-09-19 224932.png" alt="屏幕截图 2026-09-19 224932" style="zoom: 67%;" /><img src="folder_skin_tool\images\屏幕截图 2026-09-19 224936.png" alt="屏幕截图 2026-09-19 224936" style="zoom:67%;" /><img src="C:\Users\28193\AppData\Roaming\Typora\typora-user-folder_skin_tool\images\image-20260919225117291.png" alt="image-20260919225117291" style="zoom: 50%;" />

## 左右移动与默认尺寸

- 左侧「角色左右位置」移动角色；右侧「皮肤位置」页的「文件夹左右位置」移动文件夹。
- 不同宽高比不能同时匹配宽和高而不变形，因此会在对应轮廓范围内等比例适配、保留留白。匹配后仍可继续微调。
- 「恢复原构图尺寸」恢复原先的文件夹比例和位置。
- 这里匹配的是图标内部的可见比例，不能独立指定某一个桌面图标的屏幕像素大小。最终显示大小由 Windows 桌面/资源管理器的视图和缩放决定；不同尺寸的系统图标绘制也可能略有差异。

默认尺寸读取依据：[Microsoft SHGetStockIconInfo](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shgetstockiconinfo)。

## 更改系统默认文件夹皮肤

<img src="C:\Users\28193\AppData\Roaming\Typora\typora-user-folder_skin_tool\images\image-20260919225350608.png" alt="image-20260919225350608" style="zoom:50%;" />

右侧「系统默认」页提供以下功能：

- **导入 ICO**：选择已保存的 `.ico` 文件，导入时验证图标内容。此功能独立于左侧角色和文件夹构图，不需要选择 PNG 或目标文件夹。
- **设为系统默认文件夹图标**：使用导入的 ICO 原始内容（保留其尺寸，不重新合成），设为本机普通文件夹的默认图标。
- **恢复系统默认图标**：还原首次全局修改前的设置；如果原来已有其他自定义设置，则恢复那些设置。
- **刷新当前桌面图标**：在当前登录会话发送刷新通知，不关闭资源管理器。应用成功表示注册表写入并校验完成，不代表能验证桌面已经采用新图标。请以新建的普通空文件夹判断；已有单独皮肤、特殊文件夹和内容缩略图可能覆盖默认图标。若刷新后新建空文件夹仍未变化，先注销并重新登录，再判断此 Windows 版本是否支持该方式。

点击后 Windows 会请求管理员授权，取消则不执行操作。

## **注意：如果点击设为系统默认文件夹图标后，没有反应：**

按 **Ctrl＋Shift＋Esc → Windows 资源管理器 → 重新启动，即可更改所有系统默认图标，效果如下：**

![屏幕截图 2026-09-19 224240](folder_skin_tool\images\屏幕截图 2026-09-19 224240.png)

