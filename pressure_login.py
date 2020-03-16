import logging
import aiohttp
import asyncio
from cores import login
logging.basicConfig(level=logging.DEBUG)
async def get_public_course(ses:aiohttp.ClientSession)->dict:
    async with ses.get(url="https://noj.tw/api/course/Public") as resp:
        assert resp.status == 200
        data = await resp.json()
        return data

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    user_sessions = []
    tasks = []
    for i in range(100):
        tasks.append(asyncio.ensure_future(login._get_async_session(username=f"test{i}" , passwd=f"test{i}")))
    loop.run_until_complete(asyncio.wait(tasks))
    
    for t in tasks:
        user_sessions.append(t.result())
    
    tasks = []
    for s in user_sessions:
        tasks.append(asyncio.ensure_future(get_public_course(s)))
    loop.run_until_complete(asyncio.wait(tasks))
    