import aiohttp
import requests
import json
import logging
import asyncio

cfg = {}
ASYNC_SESS = None
SEQ_SESS = None


def read_cfg():
    with open("cores/config.json", "r") as f:
        global cfg
        cfg = json.loads(f.read())
        logging.debug(cfg)


def get_user_passwd(username) -> str:
    if cfg == {}:
        read_cfg()
    for i in list(cfg["users"]):
        if i["username"] == username:
            return i["passwd"]


def get_api_base() -> str:
    if cfg == {}:
        return "https://noj.tw/api"
    return cfg["API_BASE"]


async def _get_async_session(
    username: str,
    passwd: str = "",
) -> aiohttp.ClientSession:
    if passwd == "":
        passwd = get_user_passwd(username)
    ses = aiohttp.ClientSession()
    async with ses.post(
            f"{get_api_base()}/auth/session",
            json={
                'username': username,
                'password': passwd,
            },
    ) as resp:
        txt = await resp.text()
        logging.debug(f"[login raw] {txt}")
        assert resp.status == 200
    return ses


async def get_session_async(username: str):
    return await _get_async_session(username)


def get_async_session(username="first_admin") -> aiohttp.ClientSession:
    if cfg == {}:
        read_cfg()
    global ASYNC_SESS
    if ASYNC_SESS is not None:
        return ASYNC_SESS
    passwd = get_user_passwd(username)
    ASYNC_SESS = asyncio.run(_get_async_session(username, passwd))
    return ASYNC_SESS


def get_session(username="first_admin") -> requests.Session:
    if cfg == {}:
        read_cfg()
    global SEQ_SESS
    if SEQ_SESS is not None:
        return SEQ_SESS
    sess = requests.Session()
    resp = sess.post(
        f'{get_api_base()}/auth/session',
        json={
            'username': username,
            'password': get_user_passwd(username)
        },
    )

    if resp.status_code != 200:
        sess.close()
        logging.error(resp.text)
        return None
    SEQ_SESS = sess
    return sess


async def _kill_async_session(ses: aiohttp.ClientSession):
    await ses.close()


def kill_async_session(ses: aiohttp.ClientSession):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_kill_async_session(ses))
