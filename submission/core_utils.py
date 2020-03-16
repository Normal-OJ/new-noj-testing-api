from zipfile import is_zipfile
import aiohttp
import json
import requests
import logging
from time import sleep
from cores.login import get_api_base
DELAY_SEC = 1.0

async def async_submit(sess: aiohttp.ClientSession,
                       lang,
                       problem_id,
                       code=None) -> str:
    '''
    submit asynchronously `problem_id` with language `lang`
    if `code` is "", use default source decided by `lang`

    Args:
        code: the code path
    '''
    logging.debug(
        f"sending async submission with lang id: {lang} , problem id :{problem_id}")
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


async def async_get_status(sess: aiohttp.ClientSession, submissionId: str) -> dict:
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
            "time": context["timestamp"],
            "memoryUsage": context["memoryUsage"],
            "runTime": context["runTime"],
            "tasks": context["tasks"]
        }


def seq_submit(sess: requests.Session, lang: int, problem_id: int , code: "") -> str:
    API_BASE = get_api_base()
    '''
    submit `problem_id` with language `lang`
    if `code` is None, use default source decided by `lang`

    Args:
        code: the code path
    '''
    logging.info('===submission===')
    langs = ['c', 'cpp', 'py']

    # create submission
    resp = sess.post(
        f'{API_BASE}/submission',
        json={
            'languageType': lang,
            'problemId': problem_id
        },
    )

    logging.debug(f'raw resp: {resp.text}')
    rj = json.loads(resp.text)
    logging.info(rj)
    rj = rj['data']
    assert resp.status_code == 200

    # open code file
    if code == "":
        # use default
        code = open(f'{langs[lang]}-code.zip', 'rb')
    else:
        # check zip
        if not is_zipfile(code):
            logging.warning('you are submitting a non-zip file.')
        # if it is the path string
        if 'read' not in code:
            code = open(code, 'rb')

    # upload source
    resp = sess.put(
        f'{API_BASE}/submission/{rj["submissionId"]}',
        files={'code': ('scnuoqd414fwq', code)},
    )
    logging.info(resp.status_code)
    logging.info(resp.text)
    assert resp.status_code == 200
    logging.info('===end===')

def seq_get_status(sess: requests.Session, submissionId: str)->dict:
    API_BASE = get_api_base()
    with sess.get(f"{API_BASE}/submission/{submissionId}") as resp:
        logging.debug("===get_status===")
        context = resp.content
        logging.debug(f"raw text:{context}")
        context = dict(json.loads(context))
        assert resp.status_code == 200
        context = context["data"]
        logging.debug(f"status:{context}")
        logging.debug("======end ======")
        return {
            "id": context["submissionId"],
            "score": context["score"],
            "status": context["status"],
            "time": context["timestamp"],
            "memoryUsage": context["memoryUsage"],
            "runTime": context["runTime"],
            "tasks": context["tasks"]
        }

async def async_rejudge(sess:aiohttp.ClientSession , submission_id:str):
    API_BASE = get_api_base()
    if DELAY_SEC != 0:
        await asyncio.sleep(DELAY_SEC)
    
    async with sess.get(f"{API_BASE}/submission/{submission_id}/rejudge") as resp:
        logging.debug("===async rejudge===")
        context = await resp.text()
        logging.debug(f"raw text:{context}")
        logging.debug(f"content-type:{resp.content_type}")
        context = dict(json.loads(context))
        assert resp.status == 200
        logging.debug("======end ======")

def seq_rejudge(sess:requests.Session , submission_id:str):
    API_BASE = get_api_base()
    if DELAY_SEC != 0:
        sleep(DELAY_SEC)
    
    with sess.get(f"{API_BASE}/submission/{submission_id}/rejudge") as resp:
        logging.debug("===seq rejudge===")
        context = resp.content
        logging.debug(f"raw text:{context}")
        context = dict(resp.json())
        assert resp.status == 200
        logging.debug("======end ======")

def seq_handwritten_grade(sess:requests.Session , sid:str , score:int)->bool:
    base = get_api_base() + f"/submission/{sid}/grade"
    logging.debug(f"base: {base}")
    headers = {'Content-Type': 'application/json'}
    with sess.put(base , headers=headers , data=json.dumps({"score":score})) as resp:
        if resp.status_code != 200:
            logging.warn(f"handwritten update score got status code :{resp.status_code}")
            logging.warn(f"raw resp:{resp.text}")
            return False
        logging.info(f"raw resp:{resp.text}")
        return True
