# ChuangGao-iOSRealRun-Simplified
校园跑模拟工具，适用于创高体育(浙江大学(浙大体艺，据我了解就是创高体育换皮)、四川大学、南开大学)和其他iOS端的校园跑打卡软件
**适用于各类运动打卡 App，只要你的校园跑软件有iOS端就可以使用**(原理是在 iOS 设备上模拟 GPS 移动)

通过 QUIC 隧道连接设备，沿着指定的路线循环发送 WGS-84 坐标。
本项目是 [iOSRealRun-cli-17](https://github.com/iOSRealRun/iOSRealRun-cli-17) 的代码重构
底层使用 [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) 与 iOS 设备通信。

## 简明使用教程(Windows)

如果你懒得看完整个readme，可以直接：
1. 电脑百度搜索爱思助手，在电脑上下载并安装(爱思助手可能会让你装这装那的，全装了就行)，在你的iOS设备上打开开发者模式，具体操作自行搜索(可参考本文"常见问题"部分)
2. 打开爱思助手，解锁并保持你的iPhone或者iPad不锁屏(系统版本最好是iOS 18，更高版本的应该也行？更低的版本不一定行)
3. 用数据线将你的iPhone或者iPad连接到电脑，此时爱思助手应该会显示连接成功，如果爱思助手连不上，上网查一下，确保使用过程中爱思助手显示手机成功连接
4. 下载本项目的源代码，打开powershell(管理员)，cmd也行，cd将工作目录切到这个项目下
5. 在powershell里运行：pip install -r requirements.txt
6. 运行python main.py
7. 此时打开手机里的地图，可以发现定位已经变了，如果要自定义跑步的路线：可以访问：https://fakerun.myth.cx/ 自行绘制路线，复制路线到 route.txt 中，然后关闭powershell重新操作上述步骤
8. ctrl+c退出模拟跑步，如果定位没恢复可以重启设备

## 原理

1. **坐标转换** — 百度地图取点使用 BD-09 坐标系，iOS 使用 WGS-84 坐标系，程序自动完成转换。
2. **路线插值** — 在稀疏路线点之间按固定时间步长（默认 0.2 秒）插值，确保模拟的运动轨迹在目标速度下保持平滑。
3. **随机扰动** — 每圈对路线施加垂直于轨迹方向的随机偏移，配合 sin² 平滑包络，让运动轨迹看起来自然不机械。
4. **速度变化** — 每圈速度在目标值附近随机浮动，避免配速过于恒定引起怀疑。
5. **位置推送** — 通过 `pymobiledevice3` 的 DVT `LocationSimulation` 服务将坐标持续发送到设备。

## 环境要求

- **操作系统**: Windows（需安装 iTunes）或 macOS
- **iOS 版本**: 18 及以上，需开启开发者模式
- **Python**: 3.10+
- **设备连接**: 同一时间只能连接一台 iPhone/iPad

## 快速开始

建议在Windows用户在Powershell(管理员)中运行，Mac用户全程sudo
```bash
# 1. 克隆项目
git clone https://github.com/jhy354/iOSRealRunSimplified.git
cd iOSRealRunSimplified

# 2. 安装依赖（建议使用虚拟环境）
pip install -r requirements.txt

# 3. 挂载开发者磁盘镜像（每次连接设备后需要执行一次）如果报错，见下方常见问题处
pymobiledevice3 mounter auto-mount

# 4. 运行
python main.py

# 按 Ctrl+C 停止程序，注意不要直接关闭窗口，否则无法恢复定位
```

## 配置

所有配置项都有合理的默认值，无需配置即可运行。如需自定义，可以创建 `config.yaml`：

```yaml
# 速度（米/秒），3.3 ≈ 11'52"/mile 步行配速
speed: 3.3

# 路线文件路径（百度地图 BD-09 坐标）
route_file: "route.txt"

# 位置更新时间间隔（秒）
dt: 0.2

# 每圈速度最大随机浮动范围
speed_variation: 15.0

# 路线随机偏移幅度（坐标度数）
route_deviation: 0.000025

# 隧道启动超时（秒）
tunnel_timeout: 30.0

# 开启调试日志
debug: false
```

也可以通过命令行参数覆盖：

```bash
python main.py -s 5.0 -r routes/ZJU_HN.txt --debug
```

### 命令行参数

| 参数 | 说明 |
|------|------|
| `-c, --config PATH` | YAML 配置文件路径（默认：`config.yaml`） |
| `-s, --speed M/S` | 目标速度（米/秒） |
| `-r, --route PATH` | 路线文件路径 |
| `--dt SECONDS` | 位置更新时间间隔 |
| `--debug` | 开启调试日志 |
| `--manual` | 手动隧道模式（自行输入 host:port） |

## 路线文件格式

路线文件包含一串 BD-09 坐标的 JSON 对象：

```json
{"lng":"117.17...","lat":"39.11..."},{"lng":"117.17...","lat":"39.11..."},...
```

可以从[百度地图坐标拾取系统](https://api.map.baidu.com/lbsapi/getpoint/index.html)或 https://fakerun.myth.cx/ 获取 BD-09 坐标。

## 项目结构

```
iOSRealRunSimplified/
├── main.py            # 入口，命令行解析和流程编排
├── config.py          # 配置管理（dataclass + YAML 加载）
├── geo_utils.py       # BD-09 → WGS-84 坐标转换、haversine 距离计算
├── route.py           # 路线加载、时间步插值、随机扰动
├── tunnel.py          # QUIC 隧道生命周期（asyncio 子进程）
├── simulation.py      # DVT 位置模拟引擎
├── config.yaml        # 可选配置文件
├── route.txt          # 默认路线（BD-09 坐标）
├── routes/            # 额外路线文件
└── requirements.txt   # Python 依赖
```

## 常见问题

**"请连接设备后按回车"**
- 确认设备已通过 USB 连接、已解锁、已信任此电脑。
- Windows 请确认 iTunes 已安装。
- 确保只连接了一台设备。

**"无法开启开发者模式"**
- **(重要)**如果在 **设置 → 隐私与安全性** 中找不到开发者选项开关，可以在电脑上下载[爱思助手](https://www.i4.cn/)，手机通过数据线连接到电脑后，在爱思助手的 **工具箱 → 虚拟定位** 中按照提示操作，随后手机上就会出现开发者选项开关。
- 在设置中开启后需要**重启设备**并输入密码，之后重新运行程序。

**隧道启动超时或挂载镜像时报错**
- 先执行 `pymobiledevice3 mounter auto-mount` 挂载开发者磁盘镜像。
- 检查开发者模式是否开启：**设置 → 隐私与安全性 → 开发者模式**。
- **(重要)**若始终无法挂载镜像，可以在每次虚拟跑步之前打开爱思助手，确保手机与电脑连接正常后，直接在**管理员模式的 PowerShell** 中运行 `python main.py`（爱思助手在连接设备时会自动处理镜像挂载，一般只要爱思助手连上了就不会报错）。
- 若无法建立tunnel，可以关闭所有vpn工具或加速器工具后重试

**定位没有恢复**
- 使用 `Ctrl+C` 终止程序，不要直接关闭终端窗口。
- 如果定位仍未恢复，重启手机即可。

**Windows 上提示没有需要的版本**
- 尝试不使用国内 pip 源：`pip install -r requirements.txt -i https://pypi.org/simple/`
- 各个pip包版本应尽量符合requirements.txt中的要求。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。
