# DDatHome-python
DD@Home in Python<br>

[DDatHome-nodejs](https://github.com/dd-center/DDatHome-nodejs)的Python异步实现

---

## 1.1.2 版本更新

- 修复了一系列问题，项目结构有较大变化，建议重新克隆仓库，重新安装依赖

- 支持弹幕服务器转发

---

## 如何更新

1. 进入项目目录

```sh
$ cd DDatHome-python
```

2. 拉取最新代码

```sh
$ git pull
```

3. 更新依赖库

```sh
$ pip install -r requirements.txt
```

---

## 快速上手

### 所需环境

* 3.7 <= Python <= 3.9

### 克隆仓库

```sh
$ git clone https://github.com/Radekyspec/DDatHome-python.git

$ cd DDatHome-python
```

### 安装依赖

```shell
$ pip install -r requirements.txt
```

### 运行

```shell
$ python main.py
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
; 直播间连接数, 同时转发多少直播间 | 选填, 默认1000
ws_limit =
```
