# ScenAgent 云边协同部署操作手册

本文面向“不需要理解代码细节，只想把系统跑起来”的部署者。目标是：

```text
云服务器运行 ScenAgent 前后端和 frps
本地 Windows 电脑连接手机
通过 FRP 隧道让云端后端控制本地手机
```

最终访问：

```text
http://<云服务器公网 IP>:3000
```

即可在网页上提交任务，并让云端 ScenAgent 操作本地手机。

## 1. 整体架构

```text
浏览器
  -> 云服务器 frontend:3000
  -> 云服务器 backend:9000
  -> 云服务器 Docker 内网 frps:15555
  -> FRP 隧道
  -> 本地 Windows FRP 客户端
  -> 本地 127.0.0.1:5555
  -> adb forward
  -> USB 手机
```

可以把它理解为：

```text
云端负责“思考和发命令”
本地电脑负责“把 USB 手机接入云端”
```

## 2. 云服务器准备

### 2.1 开放安全组端口

在阿里云、腾讯云、华为云等控制台里，给云服务器开放：

| 端口 | 协议 | 用途 |
| :--- | :--- | :--- |
| `7000` | TCP | FRP 客户端连接云端 frps |
| `3000` | TCP | ScenAgent 前端页面 |
| `9000` | TCP | ScenAgent 后端 API |

如果这些端口没开放，本地 FRP 客户端或浏览器会连不上。

### 2.2 安装 Docker 和 Docker Compose

服务器需要能执行：

```bash
docker --version
docker compose version
```

如果没有安装 Docker，请先按服务器系统安装 Docker Engine 和 Docker Compose
Plugin。

### 2.3 准备云端部署目录

在服务器上创建一个目录，例如：

```bash
mkdir -p ~/scenagent-cloud
cd ~/scenagent-cloud
```

目录建议结构：

```text
scenagent-cloud/
  docker-compose.cloud.yml
  frp/
    frps.toml
  web/
    data/
  output/
```

创建目录：

```bash
mkdir -p frp web/data output
```

也可以直接把本目录 `cloud-edge-notes/` 上传到服务器作为部署目录使用。

## 3. 云端配置 frps

本目录已提供示例文件：

```text
frp/frps.toml
```

内容示例：

```toml
bindPort = 7000

auth.method = "token"
auth.token = "CHANGE_ME_TO_A_STRONG_TOKEN"
```

注意：

- `bindPort = 7000` 对应云服务器安全组开放的 `7000` 端口。
- 部署前必须把 `auth.token` 改成你自己的强密码。
- `auth.token` 必须和本地 FRP 客户端里填写的 Token 完全一致。
- 不要把真实 Token 发到公开仓库或截图里。

## 4. 云端 Docker Compose

本目录已提供可直接使用的 compose 文件：

```text
docker-compose.cloud.yml
```

单设备示例：

```yaml
services:
  frps:
    image: snowdreamtech/frps
    restart: always
    volumes:
      - ./frp/frps.toml:/etc/frp/frps.toml
    command: frps -c /etc/frp/frps.toml
    ports:
      - "7000:7000"

  backend:
    image: likelikec/scen-agent-backend:latest
    restart: unless-stopped
    depends_on:
      - frps
    environment:
      # 单设备：对应本地 FRP 客户端的远程端口 15555
      MOBILE_V4_DEVICES: "frps:15555"
      MOBILE_V4_OUTPUT_DIR: "output"
    volumes:
      - ./web/data:/app/web/data
      - ./output:/app/output
    ports:
      - "9000:8003"

  frontend:
    image: likelikec/scen-agent-frontend:latest
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "3000:80"
```

如果你的镜像源不是 Docker Hub，而是私有镜像仓库，请把：

```yaml
likelikec/scen-agent-backend:latest
likelikec/scen-agent-frontend:latest
```

替换成你实际部署使用的镜像名。

## 5. 启动云端服务

在 `docker-compose.cloud.yml` 所在目录执行：

```bash
docker compose -f docker-compose.cloud.yml pull
docker compose -f docker-compose.cloud.yml up -d
```

查看容器状态：

```bash
docker compose -f docker-compose.cloud.yml ps
```

查看后端日志：

```bash
docker compose -f docker-compose.cloud.yml logs -f backend
```

此时本地 FRP 客户端还没连上，所以后端可能暂时连不上 `frps:15555`，这是正常的。

## 6. 本地 Windows 准备 ADB

### 6.1 安装 Android Platform Tools

下载 Android Platform Tools，确保 PowerShell 或 CMD 可以执行：

```powershell
adb version
```

如果提示找不到 `adb`，需要把 `adb.exe` 所在目录加入系统 `PATH`，或在该目录下打开 PowerShell。

### 6.2 连接手机

1. 用 USB 线连接手机和 Windows 电脑。
2. 打开手机“开发者选项”。
3. 开启“USB 调试”。
4. 手机上出现授权弹窗时选择允许，建议勾选“始终允许”。

验证：

```powershell
adb devices
```

应看到：

```text
<设备序列号>    device
```

如果显示 `unauthorized`，请看手机屏幕确认 USB 调试授权。

### 6.3 建立本地 ADB 转发

单设备执行：

```powershell
adb forward tcp:5555 tcp:5555
```

检查：

```powershell
adb forward --list
```

应能看到类似：

```text
<设备序列号> tcp:5555 tcp:5555
```

这一步的含义是：

```text
本地 127.0.0.1:5555
  -> USB ADB 通道
  -> 手机
```

## 7. 本地 Windows 配置 FRP 客户端 GUI

打开你实际使用的 FRP 客户端图形界面。

### 7.1 配置服务器信息

填写：

| 配置项 | 示例值 |
| :--- | :--- |
| 服务器地址 | `<云服务器公网 IP>` |
| 服务器端口 | `7000` |
| Token | 与云端 `frps.toml` 的 `auth.token` 一致 |

### 7.2 创建 ADB TCP 代理

新建一个 TCP 代理，填写：

| 配置项 | 示例值 | 说明 |
| :--- | :--- | :--- |
| 代理名称 | `adb` | 名称随意 |
| 协议 | `tcp` | 必须是 TCP |
| 内网地址 | `127.0.0.1` | 本地电脑 |
| 内网端口 | `5555` | 对应 `adb forward tcp:5555 tcp:5555` |
| 外网端口 / 远程端口 | `15555` | 云端后端访问 `frps:15555` |
| 加密传输 | 可关 | 按你的 FRP 客户端设置 |
| 压缩传输 | 可关 | 按你的 FRP 客户端设置 |

保存并启动代理。

启动成功后，云端后端访问：

```text
frps:15555
```

就会通过 FRP 隧道到达本地：

```text
127.0.0.1:5555
```

再通过 `adb forward` 到手机。

## 8. 验证全链路

### 8.1 看本地 FRP 客户端

确认代理状态是运行中，日志里没有认证失败、端口占用、连接超时。

常见成功信息通常包含：

```text
start proxy success
```

不同 GUI 文案可能不同，以“代理已启动/连接成功”为准。

### 8.2 看云端后端日志

在云服务器执行：

```bash
docker compose -f docker-compose.cloud.yml logs -f backend
```

如果后端启动时或任务运行前成功连接设备，通常会看到类似：

```text
Successfully connected to frps:15555
Ensuring device connected: frps:15555
```

### 8.3 打开前端

浏览器访问：

```text
http://<云服务器公网 IP>:3000
```

如果前端页面需要填写后端地址，填写：

```text
http://<云服务器公网 IP>:9000
```

然后提交任务测试。

## 9. 多设备配置

多设备时，每台手机需要一组独立端口。

### 9.1 本地 ADB 转发

假设本地接了三台手机，可以手动执行：

```powershell
adb devices
adb -s <手机1序列号> forward tcp:5555 tcp:5555
adb -s <手机2序列号> forward tcp:5556 tcp:5555
adb -s <手机3序列号> forward tcp:5557 tcp:5555
```

也可以使用已有脚本：

```text
云边协同部署/multi_device_forward.bat
```

该脚本会从 `5555` 开始自动给本地设备分配端口。

### 9.2 FRP 客户端创建多条代理

| 手机 | 本地地址 | 本地端口 | 远程端口 |
| :--- | :--- | :--- | :--- |
| 手机 1 | `127.0.0.1` | `5555` | `15555` |
| 手机 2 | `127.0.0.1` | `5556` | `15556` |
| 手机 3 | `127.0.0.1` | `5557` | `15557` |

### 9.3 云端后端配置多设备

修改 `docker-compose.cloud.yml`：

```yaml
backend:
  environment:
    MOBILE_V4_DEVICES: "frps:15555,frps:15556,frps:15557"
```

重启后端：

```bash
docker compose -f docker-compose.cloud.yml up -d backend
```

注意：设备池是在后端进程启动时创建的，修改 `MOBILE_V4_DEVICES` 后必须重启后端。

## 10. 模拟器配置

如果本地使用模拟器，而不是 USB 真机，先确认模拟器 ADB 端口。

常见情况：

| 模拟器 | 常见 ADB 地址 |
| :--- | :--- |
| Android Studio AVD | `127.0.0.1:5555` 或 `emulator-5554` |
| MuMu 模拟器 12 | 通常为 `127.0.0.1:7555` |
| 雷电模拟器 | 通常为 `127.0.0.1:5555` |

例如 MuMu 端口是 `7555`，则 FRP 客户端代理填写：

```text
内网地址：127.0.0.1
内网端口：7555
远程端口：15555
```

云端后端仍然写：

```yaml
MOBILE_V4_DEVICES: "frps:15555"
```

## 11. 常见问题

### Q1：后端报 `Device frps:15555 is offline`

检查：

1. 本地 FRP 客户端代理是否启动。
2. FRP 远程端口是否是 `15555`。
3. 云端 `MOBILE_V4_DEVICES` 是否是 `frps:15555`。
4. 本地是否已经执行 `adb forward tcp:5555 tcp:5555`。
5. 手机是否还在线，执行 `adb devices` 查看。

### Q2：FRP 客户端连接失败

检查：

1. 云服务器安全组是否开放 `7000`。
2. FRP 客户端服务器地址是否填云服务器公网 IP。
3. FRP 客户端 Token 是否和云端 `frps.toml` 完全一致。
4. 云端 `frps` 容器是否正在运行：

   ```bash
   docker compose -f docker-compose.cloud.yml ps
   docker compose -f docker-compose.cloud.yml logs -f frps
   ```

### Q3：本地 `adb forward` 失败

检查：

1. `adb devices` 是否能看到手机。
2. 手机是否授权 USB 调试。
3. 端口是否被占用。
4. 多设备时是否加了 `-s <设备序列号>`。

### Q4：只在服务器装 ADB 行不行？

如果手机在本地 Windows，通过 FRP 接入：不行。两边都需要。

```text
服务器 ADB：负责发控制命令
本地 ADB：负责识别 USB 手机并建立 adb forward
```

如果代码和模拟器都在服务器上，则只需要服务器有 ADB。

### Q5：`MOBILE_V4_DEVICES` 可以不写吗？

本地裸跑 Python 时可以不写，后端会尝试 `adb devices` 自动识别。

云端 Docker + FRP 场景必须写，例如：

```yaml
MOBILE_V4_DEVICES: "frps:15555"
```

否则云端容器不知道应该连接哪个远程手机。

## 12. 关键配置速查

单设备最小配置：

```text
云服务器安全组：
  7000, 3000, 9000

云端 frps：
  bindPort = 7000
  auth.token = 同一个 Token

本地 adb：
  adb devices
  adb forward tcp:5555 tcp:5555

本地 FRP 客户端：
  服务器地址 = 云服务器公网 IP
  服务器端口 = 7000
  Token = 同一个 Token
  TCP 代理：127.0.0.1:5555 -> 15555

云端 backend：
  MOBILE_V4_DEVICES=frps:15555

浏览器：
  http://<云服务器公网 IP>:3000
```
