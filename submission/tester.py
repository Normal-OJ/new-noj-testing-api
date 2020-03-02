import click
import asyncio
import logging
import aiohttp
import time
import json
from zipfile import is_zipfile
from cores.login import get_async_session, get_api_base,kill_async_session

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


def get_result(session: aiohttp.ClientSession, submissionIds: list , submission_time_limit={} , MAX_TIMEOUT = 3600) -> dict:
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
                    result[submissionId] = "timeout...QQ"
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
            result.update({"status": "timeout"})
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
@click.argument("count", type=int, default=1)
@click.argument("lang", type=int, default=0)
@click.argument("problem_id", type=int, default=1)
@click.argument("code", type=click.Path(file_okay=True), default="")
@click.option("--pressure",
              "-p",
              help="mount an submission pressure test base on given count")
def pressure_tester(count: int, lang: int, problem_id: int, code: str,
                    pressure):
    ses = get_async_session()
    assert ses != None

    tasks = []
    for i in range(count):
        tasks.append(
            asyncio.ensure_future(_submit(ses, lang, problem_id, code)))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    submissionIds = []
    for task in tasks:
        submissionIds.append(task.result())
    result = get_result(ses, submissionIds)
    kill_async_session(ses)
    with open("result.json", "w") as f:
        f.write(json.dumps(result, indent=4))
