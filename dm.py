from __future__ import annotations

import asyncio
import aiohttp
import json
import threading
import traceback
import random
import string

import brotli
import websockets

from logger import Logger


class BiliDM(threading.Thread):
    def __init__(self, room_id, ws):
        super().__init__(name=f"Room-{room_id}", daemon=True)
        self.ws = ws
        self.bili_ws = None
        self.room_id = str(room_id)
        self.logger = Logger(logger_name="live-ws").get_logger()
        self.wss_url = "wss://broadcastlv.chat.bilibili.com/sub"
        self.closed = False

    def set_ws(self, ws_client):
        self.ws = ws_client

    @property
    def _uuid(self):
        digits: list[str] = [
            "".join(random.sample(string.hexdigits, 8)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 4)),
            "".join(random.sample(string.hexdigits, 17))
        ]
        uuid: str = "-".join(digits).upper() + "infoc"
        return uuid

    async def get_key(self):
        url = "https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo"
        payload = {
            "id": self.room_id,
            "type": 0,
        }
        headers = {
            "cookie": f"buvid3={self._uuid}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/102.0.0.0 Safari/537.36",
        }
        async with aiohttp.request("GET", url, params=payload, headers=headers) as resp:
            # self.wss_url = self.wss_url + resp["data"]["host_list"][0]["host"] + "/sub"
            resp = json.loads(await resp.text(encoding="utf-8"))
            return resp["data"]["token"]

    async def startup(self):
        key = await self.get_key()
        payload = json.dumps(
            {
                "uid": 0,
                "roomid": int(self.room_id),
                "protover": 3,
                "platform": "web",
                "type": 2,
                "key": key
            },
            separators=(",", ":")
        )
        header_op = "001000010000000700000001"
        header_len = ("0" * (8 - len(hex(len(payload) + 16)[2:])) + hex(len(payload) + 16)[2:]) if len(
            hex(len(payload) + 16)[2:]) <= 8 else ...
        header = header_len + header_op + \
                 bytes(str(payload), encoding="utf-8").hex()
        headers = {
            "cookie": f"buvid3={self._uuid}",
            "origin": "https://live.bilibili.com",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/102.0.0.0 Safari/537.36",
        }
        async for self.bili_ws in websockets.connect(self.wss_url,
                                                     extra_headers=headers,
                                                     open_timeout=None):
            await self.bili_ws.send(bytes.fromhex(header))
            self.logger.debug(
                "[{room_id}]  Connected to danmaku server.".format(room_id=self.room_id))
            tasks = [asyncio.create_task(self.heart_beat(self.bili_ws)),
                     asyncio.create_task(self.receive_dm(self.bili_ws))]
            try:
                await asyncio.gather(*tasks)
            except websockets.ConnectionClosed:
                [task.cancel() for task in tasks]
                if not self.closed:
                    self.logger.debug(
                        "[{room_id}]  Reconnecting to danmaku server.".format(room_id=self.room_id))
                    continue
                break
            except RuntimeError:
                pass

    async def heart_beat(self, ws):
        # [object Object]
        hb = "0000001f0010000100000002000000015b6f626a656374204f626a6563745d"
        while not self.closed:
            await asyncio.sleep(60)
            await ws.send(bytes.fromhex(hb))
            self.logger.debug(
                "[{room_id}][HEARTBEAT]  Send HeartBeat.".format(room_id=self.room_id))

    async def receive_dm(self, ws):
        while not self.closed:
            receive_text = await ws.recv()
            if receive_text:
                await self.process_dm(receive_text)
            await asyncio.sleep(0.1)

    @staticmethod
    def _dumps(data):
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    async def process_dm(self, data, is_decompressed=False):
        # 获取数据包的长度，版本和操作类型
        packet_len = int(data[:4].hex(), 16)
        ver = int(data[6:8].hex(), 16)
        op = int(data[8:12].hex(), 16)

        # 有的时候可能会两个数据包连在一起发过来，所以利用前面的数据包长度判断，
        if len(data) > packet_len:
            task = asyncio.create_task(self.process_dm(data[packet_len:]))
            data = data[:packet_len]
            await task

        # brotli 压缩后的数据
        if ver == 3 and not is_decompressed:
            data = brotli.decompress(data[16:])
            await self.process_dm(data, is_decompressed=True)
            return

        # ver 为1的时候为进入房间后或心跳包服务器的回应。op 为3的时候为房间的人气值。
        if ver == 1 and op == 3:
            attention = int(data[16:].hex(), 16)
            self.logger.debug(
                "[{room_id}][ATTENTION]  {attention}".format(room_id=self.room_id, attention=attention))
            await self.ws.send(json.dumps(
                {
                    "relay": {
                        "roomid": self.room_id,
                        "e": "heartbeat",
                        "data": attention
                    }
                }
            ))
            return

        # ver 不为2也不为1目前就只能是0了，也就是普通的 json 数据。
        # op 为5意味着这是通知消息，cmd 基本就那几个了。
        if op == 5:
            try:
                jd = json.loads(data[16:].decode('utf-8', errors='ignore'))
                if jd["cmd"].startswith("DANMU_MSG"):
                    info = jd["info"]
                    if not info[0][9]:
                        mid = info[2][0]
                        timestamp = info[0][4]
                        await self.ws.send(self._dumps(
                            {
                                "relay": {
                                    "roomid": self.room_id,
                                    "e": "DANMU_MSG",
                                    "data": {
                                        "message": info[1],
                                        "uname": info[2][1],
                                        "timestamp": timestamp,
                                        "mid": mid,
                                    },
                                    "token": f"{self.room_id}_DANMU_MSG_{mid}_{timestamp}"
                                }
                            }
                        ))
                elif jd["cmd"] == "LIVE":
                    await self.ws.send(self._dumps(
                        {
                            "relay": {
                                "roomid": self.room_id,
                                "e": "LIVE"
                            }
                        }
                    ))
                elif jd["cmd"] == "PREPARING":
                    await self.ws.send(self._dumps(
                        {
                            "relay": {
                                "roomid": self.room_id,
                                "e": "PREPARING"
                            }
                        }
                    ))
                elif jd["cmd"] == "ROUND":
                    await self.ws.send(self._dumps(
                        {
                            "relay": {
                                "roomid": self.room_id,
                                "e": "ROUND"
                            }
                        }
                    ))
                elif jd["cmd"] == "SEND_GIFT":
                    data = jd["data"]
                    mid = data["uid"]
                    tid = data["tid"]
                    await self.ws.send(self._dumps(
                        {
                            "relay": {
                                "roomid": self.room_id,
                                "e": "SEND_GIFT",
                                "data": {
                                    "coinType": data["coin_type"],
                                    "giftId": data["giftId"],
                                    "totalCoin": data["total_coin"],
                                    "uname": data["uname"],
                                    "mid": mid
                                },
                                "token": f"{self.room_id}_SEND_GIFT_{mid}_{tid}"
                            }
                        }
                    ))
                elif jd["cmd"] == "GUARD_BUY":
                    data = jd["data"]
                    mid = data["uid"]
                    start_time = data["start_time"]
                    await self.ws.send(self._dumps(
                        {
                            "relay": {
                                "roomid": self.room_id,
                                "e": "GUARD_BUY",
                                "data": {
                                    "mid": mid,
                                    "uname": data["username"],
                                    "num": data["num"],
                                    "price": data["price"],
                                    "giftId": data["gift_id"],
                                    "level": data["guard_level"]
                                },
                                "token": f"{self.room_id}_GUARD_BUY_{mid}_{start_time}"
                            }
                        }
                    ))
            except Exception:
                self.logger.error(traceback.format_exc())

    def run(self) -> None:
        try:
            asyncio.set_event_loop(asyncio.new_event_loop())
            asyncio.get_event_loop().run_until_complete(self.startup())
        except KeyboardInterrupt:
            print("exit with keyboard")

    async def stop(self):
        self.closed = True
        if self.bili_ws is not None:
            await self.bili_ws.close()
