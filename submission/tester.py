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
    logging.debug(
        f"sending submission with lang id: {lang} , problem id :{problem_id}")
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
            "time": context["timestamp"],
            "memoryUsage": context["memoryUsage"],
            "runTime": context["runTime"],
            "tasks": context["tasks"]
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
                    result[submissionId] = {
                        "wait_status": f"timeout expire {submission_time_limit[submissionId]} sec...QQ"}
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
                if result[k] == None:
                    result[k] = {}
            result.update({"wait_status": "timeout expire max waiting time"})

            return result

        fn_flag = True
        for k in submissionIds:
            if result[k] == None:
                fn_flag = False
                break

        if fn_flag == True:
            break
    return result


def __fuzz_compare_unit(domain: list, target: dict, filters: dict) -> list:
    logging.debug(f"target:{target}")
    logging.debug(f"filters:{filters}")
    target_keys = list(set(domain))
    target_keys = list(set(target_keys).intersection(
        set(list(filters.keys()))))
    failure_list = []
    for k in target_keys:
        if k in target:
            if target[k] != filters[k]:
                failure_list.append(
                    {"key": k, "real": target[k], "type": "abs", "expect": filters[k]})
        elif str(k).find("Max") != -1:
            key = str(k).replace("Max", "", 1)
            fit_ks = ["Max"+key, "Min"+key]
            tar_k = key[0].lower() + key[1:]
            if tar_k not in target:
                failure_list.append(
                    {"type": "miss", "key": tar_k})
                continue

            if filters[fit_ks[1]] <= target[tar_k] and target[tar_k] <= filters[fit_ks[0]]:
                pass
            else:
                failure_list.append(
                    {"key": tar_k, "real": target[tar_k], "type": "seq", "expect": (filters[fit_ks[1]], filters[fit_ks[0]])})

        else:
            failure_list.append(
                {"type": "miss", "key": k})
    return failure_list


def print_fails(fails: list) -> list:
    p_f = []
    for it in fails:
        if it["type"] == "miss":
            p_f.append(
                f"failure on {it['key']} : can not found data with key {it['key']}")
        elif it["type"] == "abs":
            p_f.append(
                f"failure on {it['key']} : expected {it['expect']} but got {it['real']}")
        elif it["type"] == "seq":
            p_f.append(
                f"failure on {it['key']} : expected between {it['expect'][0]} and {it['expect'][1]} but got {it['real']}")
        else:
            raise Exception(f"Undefind Property {it['type']}")
    return p_f


def filter_unit(target: dict, filters: dict) -> list:
    failure_list = []
    f_items = __fuzz_compare_unit(
        ["MaxMemoryUsage", "MaxRunTime", "score", "status"], target, filters)

    failure_list.extend(print_fails(f_items))
    if "tasks" in filters:
        for i in list(filters["tasks"].keys()):
            els = str(i).split(":")
            task = int(els[0])
            case = int(els[1])
            subtask = {}
            logging.debug(f"target:{target}")
            try:
                subtask = target["tasks"][task]["cases"][case]
            except (IndexError,KeyError):
                failure_list.append(
                    f"failure on task {task} case {case}: data does not exist")
                continue

            if subtask != {}:
                sub_fails = __fuzz_compare_unit(
                    ["stdout", "stderr", "exitCode", "MaxExecTime", "MaxMemoryUsage", "status"], subtask, filters["tasks"][i])
                for i in range(len(sub_fails)):
                    sub_fails[i]["key"] = f"task {task} case {case} {sub_fails[i]['key']}"

                failure_list.extend(print_fails(sub_fails))
    return failure_list


def full_filter(raw_data: dict, filters: dict) -> (dict, bool):
    overall_sucess = True
    for sid in list(raw_data.keys()):
        if type(raw_data[sid]) == str:
            continue
        logging.debug(f"raw_data[sid]:{raw_data[sid]}")
        src_file = raw_data[sid]["src"]
        if src_file in filters:
            fil = filters[src_file]
            fails = filter_unit(raw_data[sid], fil)
            if len(fails) != 0:
                overall_sucess = False
                raw_data[sid].update({"success": False})
                raw_data[sid].update({"fails": fails})
            else:
                raw_data[sid].update({"success": True})
    return raw_data, overall_sucess


@submission.command()
@click.option("-c", "--count", "count", type=int, default=0, help="the request count to send")
@click.option("-l", "--lang", "lang", type=int, default=0, help="the language of submission(non-checked)")
@click.option("-f", "--file", "code", type=click.Path(file_okay=True), default="", help="the submission source file")
@click.option("-r", "--random", "rand", type=bool, default=False, help="send the submission in random order")
@click.option("-d", "--delay", "delay", type=float, default=1.0, help="set the delay of checking up function(which will affect the accurrency of testing)")
@click.option("--maxTime", "max_time", type=float, default=3600, help="the maxium waiting time for waiting all the result(default is 3600 sec)")
@click.option("-p", "--pid", "problem_id", type=int, default=1, help="the problem id you want to submit")
@click.option("--cfg", "config", type=click.Path(file_okay=True), default="", help="the config file of this test , which will ignores \"-c\",\"-l\",\"-f\",\"-p\",\"--cmp\"")
@click.option("--fname", "fname", type=str, default="result.json", help="the filename of result(default is result.json)")
def pressure_tester(count: int, lang: int, code: str, rand: bool, delay: float, config: str, max_time: float, problem_id: int, fname: str):
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
            codes[i] = (lang, problem_id, f"{code}/" + codes[i])
        assert len(codes) >= count
    else:
        for i in range(count):
            codes.append((lang, problem_id, code))

    filters = {}
    if config != "":
        with open(config, "r") as f:
            logging.debug(f"open {config}")
            filters = f.read()
            filters = dict(json.loads(filters))
        codes = []
        for k in filters.keys():
            lt = lang
            pid = problem_id
            if "languageType" in filters[k]:
                lt = filters[k]["languageType"]
            if "problem_id" in filters[k]:
                pid = filters[k]["problem_id"]

            if "counts" in filters[k]:
                for _ in range(filters[k]["counts"]-1):
                    codes.append((lt, pid, k))
            codes.append((lt, pid, k))

        if count == 0:
            count = len(codes)

    if rand:
        random.shuffle(codes)

    tasks = []
    logging.debug(f"total count to send : {count}")
    for i in range(count):
        tasks.append(
            asyncio.ensure_future(_submit(ses, codes[i][0], codes[i][1], codes[i][2])))

    # purify codes to store only src of codes
    for i in range(len(codes)):
        codes[i] = codes[i][2]

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    submissionIds = []
    for task in tasks:
        submissionIds.append(task.result())

    get_result_filiter = {}
    if filters != {}:
        for i in range(len(submissionIds)):
            if codes[i] in filters and "expireTime" in filters[codes[i]]:
                get_result_filiter.update(
                    {submissionIds[i]: filters[codes[i]]["expireTime"]})

    result = get_result(
        ses, submissionIds, submission_time_limit=get_result_filiter, MAX_TIMEOUT=max_time)
    kill_async_session(ses)

    if code != "" or config != "":
        for i in range(len(submissionIds)):
            result[submissionIds[i]].update({"src": codes[i]})
    if config != "":
        result, all_pass = full_filter(result, filters)
        result.update({"passTest": all_pass and "wait_status" not in result})

    with open(fname, "w") as f:
        f.write(json.dumps(result, indent=4))
