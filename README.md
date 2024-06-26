# DDatHome-python
DD@Home in Python<br>

[DDatHome-nodejs](https://github.com/dd-center/DDatHome-nodejs)的Python实现

---

## 1.3.0 版本更新

- 增加了网络接口的设置, 可以自由选用IPv4/IPv6
- 修改了请求间隔逻辑
- 捕捉了一些请求异常
- 暂停弹幕采集
- 更改为多线程任务获取与分发

---

## 如何更新

1. 进入项目目录

```sh
cd DDatHome-python
```

2. 拉取最新代码

```sh
git pull
```

3. 更新依赖库

```sh
pip install -r requirements.txt
```

---

## 快速上手

### 所需环境

* 3.7 <= Python <= 3.11

### 克隆仓库

```sh
git clone https://github.com/Radekyspec/DDatHome-python.git

cd DDatHome-python
```

### 安装依赖

```shell
pip install -r requirements.txt
```

### 运行

```shell
python main.py
```

---

## 配置文件

首次运行时会自动生成带注释的`config.ini`配置文件. 可按需编辑.

### 结构详解

```script
[Settings]
; UUID | 选填, 留空为随机生成, 用于记录状态
uuid =
; 昵称 | 选填, 会显示在统计中
name =
; 请求间隔时间 (毫秒), 包括拉取任务间隔和请求API间隔 | 选填, 默认1000
interval =
; 最大队列长度, 超出将不再获取新任务 | 选填, 默认10
max_size =
; 直播服务器连接数, 同时转发多少直播间 | 选填, 默认1000
ws_limit =

[Network]
; IP协议, ipv4/ipv6/同时使用(both) | 通常无需设置, 默认both
ip = [ipv4/ipv6/both]
```

---

## 性能

### 最低配置

* CPU: 1核，能跑起来就行

* 内存: 1G, 能跑起来就行

* 磁盘: 能跑起来系统就行

* 网络: 能上网, 打开B站就行

### 推荐配置

* CPU: 1核，能跑起来就行

* 内存: 独享内存, `50M` 本体 + 每 `1000个直播服务器连接` 加 `150M`

* 磁盘: 独享50M, 用于保存日志和配置文件

* 网络: 有线网络连接
