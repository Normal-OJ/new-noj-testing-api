import click
import asyncio
import logging
import aiohttp
import random
import time
import json
from zipfile import is_zipfile
from cores.login import get_async_session, get_api_base, kill_async_session
import os.path as path
from os import listdir

DELAY_SEC = 1.0


@click.group()
def submission():
    '''
        testing for submission , involving pressure test and etc.
    '''
    pass


async def _submit(sess: aiohttp.ClientSession,
                  lang,
                  problem_id,
                  code=None) -> str:
    '''
    submit `problem_id` with language `lang`
    if `code` is "", use default source decided by `lang`

    Args:
        code: the code path
    '''
    API_BASE = get_api_base()
    logging.debug('===submission===')
    langs = ['c', 'cpp', 'py']

    # create submission
    async with sess.post(f'{API_BASE}/submission',
                         json={
                             'languageType': lang,
                             'problemId': problem_id
                         }) as resp:
        rj = await resp.json()
        rc = resp.status
        logging.debug(f"create submission return code:{rc}")
        logging.debug(rj)
        rj = rj['data']
        assert rc == 200

        # open code file
        if code is "":
            # use default
            code = open(f'{langs[lang]}-code.zip', 'rb')
        else:
            # check zip
            if not is_zipfile(code):
                logging.warning('you are submitting a non-zip file.')
            # if it is the path string
            if 'read' not in code:
                code = open(code, 'rb')

        form = aiohttp.FormData(quote_fields=False)
        form.add_field("code", code, content_type="multipart/form-data")
        # upload source
        async with sess.put(f'{API_BASE}/submission/{rj["submissionId"]}',
                            data=form) as resp2:
            status_code = resp2.status
            status_text = await resp2.text()
            logging.debug(status_code)
            logging.debug(status_text)
            assert resp2.status == 200, resp2.status
            logging.debug('===end===')
            return rj["submissionId"]


async def get_status(sess: aiohttp.ClientSession, submissionId: str) -> dict:
    API_BASE = get_api_base()
    if DELAY_SEC != 0:
        await asyncio.sleep(DELAY_SEC)
    async with sess.get(f"{API_BASE}/submission/{submissionId}") as resp:
        logging.debug("===get_status===")
        context = await resp.text()
        logging.debug(f"raw text:{context}")
        logging.debug(f"content-type:{resp.content_type}")
        context = json.loads(context)
        assert resp.status == 200
        context = context["data"]
        logging.debug(f"status:{context}")
        logging.debug("======end ======")
        return {
            "id": context["submissionId"],
            "score": context["score"],
            "status": context["status"],
            "time": context["timestamp"]
        }


def get_result(session: aiohttp.ClientSession, submissionIds: list, submission_time_limit={}, MAX_TIMEOUT=3600) -> dict:
    loop = asyncio.get_event_loop()
    result = {}
    for submissionId in submissionIds:
        result.update({submissionId: None})
    begin_time = time.time()

    while (True):
        tasks = []
        for submissionId in submissionIds:
            if result[submissionId] == None:
                if submissionId in submission_time_limit and time.time() - begin_time >= submission_time_limit[submissionId]:
                    result[submissionId] = {"status": "timeout...QQ"}
                    continue
                tasks.append(
                    asyncio.ensure_future(get_status(session, submissionId)))

        loop.run_until_complete(asyncio.wait(tasks))

        for task in tasks:
            res = dict(task.result())
            if res["status"] == -1:
                continue
            submissionId = res["id"]
            res.pop("id")
            res["time"] = time.time() - res["time"]
            result[submissionId] = res

        if time.time() - MAX_TIMEOUT >= begin_time:
            logging.info("time's up")
            for k in list(result.keys()):
                result[k] = {}
            result.update({"status": "timeout expire max waiting time"})

            return result

        fn_flag = True
        for k in submissionIds:
            if result[k] == None:
                fn_flag = False
                break

        if fn_flag == True:
            break
    return result


@submission.command()
@click.option("-c", "--count", "count", type=int, default=1, help="the request count to send")
@click.option("-l", "--lang", "lang", type=int, default=0, help="the language of submission(non-checked)")
@click.option("-f", "--file", "code", type=click.Path(file_okay=True), default="", help="the submission source file")
@click.option("-r", "--random", "rand", type=bool, default=False, help="send the submission in random order")
@click.option("-d", "--delay", "delay", type=float, default=1.0, help="set the delay of checking up function(which will affect the accurrency of testing)")
@click.option("--cmp", "compare", type=click.Path(file_okay=True), default="", help="compare the result with given json file")
@click.option("--maxTime", "max_time", type=float, default=3600, help="the maxium waiting time for waiting all the result(default is 3600 sec)")
@click.option("-p", "--pid", "problem_id", type=int, default=1, help="the problem id you want to submit")
@click.option("--cfg", "config", type=click.Path(file_okay=True), default="", help="the config file of this test")
@click.option("--fname", "fname" ,type=str , default="result.json" , help="the filename of result(default is result.json)")
def pressure_tester(count: int, lang: int, code: str, rand: bool, delay: float, compare: str, max_time: float, problem_id: int , config:str , fname:str):
    '''
    mount a submission pressure test on given condiction
    '''
    ses = get_async_session()
    assert ses != None

    DELAY_SEC = delay
    codes = []

    if code != "" and path.isdir(code):
        codes = listdir(code)
        for i in range(len(codes)):
            codes[i] = f"{code}/" + codes[i]
        assert len(codes) >= count
    else:
        for i in range(count):
            codes.append(code)

    if rand:
        random.shuffle(codes)

    tasks = []
    for i in range(count):
        tasks.append(
            asyncio.ensure_future(_submit(ses, lang, problem_id, codes[i])))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    submissionIds = []
    for task in tasks:
        submissionIds.append(task.result())
    result = get_result(ses, submissionIds, MAX_TIMEOUT=max_time)
    kill_async_session(ses)

    if code != "":
        for i in range(len(submissionIds)):
            result[submissionIds[i]].update({"src": codes[i]})
    with open(fname, "w") as f:
        f.write(json.dumps(result, indent=4))
