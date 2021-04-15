import click
import asyncio
import logging
import aiohttp
import random
import time
import json
from typing import Any, Dict, List, Tuple
from . import submission
from cores.util import as_sync
from .core_utils import async_get_status, async_submit
from cores.login import get_session_async
from pathlib import Path


async def get_result(
    session: aiohttp.ClientSession,
    submission_ids: List[str],
    submission_time_limit={},
    MAX_TIMEOUT=3600,
) -> dict:
    result = {_id: None for _id in submission_ids}
    begin_time = time.time()

    while True:
        tasks = []
        for _id in submission_ids:
            if result[_id] is not None:
                continue
            if _id in submission_time_limit and time.time(
            ) - begin_time >= submission_time_limit[_id]:
                result[_id] = {
                    "wait_status":
                    f"timeout expire {submission_time_limit[_id]} sec...QQ"
                }
                continue
            tasks.append(async_get_status(session, _id))
        tasks = await asyncio.gather(*tasks)
        # record submission results
        for task in tasks:
            res = dict(task)
            if res["status"] == -1:
                continue
            _id = res["id"]
            res.pop("id")
            res["time"] = time.time() - res["time"]
            result[_id] = res
        # timeout
        if time.time() - MAX_TIMEOUT >= begin_time:
            logging.info("time's up")
            result = {k: v for k, v in result.items() if v is not None}
            result.update({
                "wait_status": "timeout expire max waiting time",
            })
            return result
        # finish all submissions
        if all(result[k] is not None for k in submission_ids):
            break
    return result


def __fuzz_compare_unit(domain: list, target: dict, filters: dict) -> list:
    logging.debug(f"target:{target}")
    logging.debug(f"filters:{filters}")
    target_keys = list(set(domain))
    target_keys = list(
        set(target_keys).intersection(set(list(filters.keys()))))
    failure_list = []
    for k in target_keys:
        if k in target:
            if target[k] != filters[k]:
                failure_list.append({
                    "key": k,
                    "real": target[k],
                    "type": "abs",
                    "expect": filters[k]
                })
        elif str(k).find("Max") != -1:
            key = str(k).replace("Max", "", 1)
            fit_ks = ["Max" + key, "Min" + key]
            tar_k = key[0].lower() + key[1:]
            if tar_k not in target:
                failure_list.append({"type": "miss", "key": tar_k})
                continue

            if filters[fit_ks[1]] <= target[tar_k] and target[
                    tar_k] <= filters[fit_ks[0]]:
                pass
            else:
                failure_list.append({
                    "key":
                    tar_k,
                    "real":
                    target[tar_k],
                    "type":
                    "seq",
                    "expect": (filters[fit_ks[1]], filters[fit_ks[0]])
                })

        else:
            failure_list.append({"type": "miss", "key": k})
    return failure_list


def print_fails(fails: list) -> list:
    p_f = []
    for it in fails:
        if it["type"] == "miss":
            p_f.append(
                f"failure on {it['key']} : can not found data with key {it['key']}"
            )
        elif it["type"] == "abs":
            p_f.append(
                f"failure on {it['key']} : expected {it['expect']} but got {it['real']}"
            )
        elif it["type"] == "seq":
            p_f.append(
                f"failure on {it['key']} : expected between {it['expect'][0]} and {it['expect'][1]} but got {it['real']}"
            )
        else:
            raise Exception(f"Undefind Property {it['type']}")
    return p_f


def filter_unit(
    target: dict,
    filters: dict,
) -> list:
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
            except (IndexError, KeyError):
                failure_list.append(
                    f"failure on task {task} case {case}: data does not exist")
                continue

            if subtask != {}:
                sub_fails = __fuzz_compare_unit([
                    "stdout", "stderr", "exitCode", "MaxExecTime",
                    "MaxMemoryUsage", "status"
                ], subtask, filters["tasks"][i])
                for i in range(len(sub_fails)):
                    sub_fails[i][
                        "key"] = f"task {task} case {case} {sub_fails[i]['key']}"

                failure_list.extend(print_fails(sub_fails))
    return failure_list


def full_filter(
    raw_data: Dict[str, Any],
    filters: dict,
) -> Tuple[dict, bool]:
    overall_sucess = True
    for sid, d in raw_data.items():
        if type(d) == str:
            continue
        logging.debug(f"raw_data[{sid}]: {d}")
        src_file = d["src"]
        if src_file in filters:
            fil = filters[src_file]
            fails = filter_unit(d, fil)
            if len(fails) != 0:
                overall_sucess = False
                d.update({
                    "success": False,
                    "fails": fails,
                })
            else:
                d.update({"success": True})
    return raw_data, overall_sucess


@submission.command()
@click.option(
    "-u",
    "--user",
    "user",
    type=str,
    default="first_admin",
    help="the user to login as",
)
@click.option(
    "-c",
    "--count",
    "count",
    type=int,
    default=0,
    help="the request count to send",
)
@click.option(
    "-l",
    "--lang",
    "lang",
    type=int,
    default=0,
    help="the language of submission(non-checked)",
)
@click.option(
    "-f",
    "--file",
    "code",
    type=click.Path(file_okay=True),
    default="",
    help="the submission source file",
)
@click.option(
    "-r",
    "--random",
    "rand",
    type=bool,
    default=False,
    help="send the submission in random order",
)
@click.option(
    "-d",
    "--delay",
    "delay",
    type=float,
    default=1.0,
    help=
    "set the delay of checking up function(which will affect the accurrency of testing)",
)
@click.option(
    "--maxTime",
    "max_time",
    type=float,
    default=3600,
    help=
    "the maxium waiting time for waiting all the result(default is 3600 sec)",
)
@click.option(
    "-p",
    "--pid",
    "problem_id",
    type=int,
    default=1,
    help="the problem id you want to submit",
)
@click.option(
    "--cfg",
    "config",
    type=click.Path(file_okay=True),
    default="",
    help="the config file of this test , which "
    "will may overwrite some other options , "
    "see wiki for more detailed",
)
@click.option(
    "--fname",
    "fname",
    type=str,
    default="result.json",
    help="the filename of result(default is result.json)",
)
@as_sync
async def pressure_tester(
    user: str,
    count: int,
    lang: int,
    code: str,
    rand: bool,
    delay: float,
    config: str,
    max_time: float,
    problem_id: int,
    fname: str,
):
    '''
    mount a submission pressure test on given condiction
    '''
    ses = await get_session_async(user)
    assert ses != None
    global DELAY_SEC
    DELAY_SEC = delay
    # prepare codes
    codes = []
    if code != "" and Path(code).is_dir():
        code_dir = Path(code)
        for ch in code_dir.iterdir():
            codes.append((lang, problem_id, str(ch)))
        assert len(codes) >= count
    else:
        codes = [(lang, problem_id, code)] * count
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
                for _ in range(filters[k]["counts"] - 1):
                    codes.append((lt, pid, k))
            codes.append((lt, pid, k))
        if count == 0:
            count = len(codes)
    if rand:
        random.shuffle(codes)
    logging.debug(f"total count to send : {count}")
    # submit to judge
    tasks = [async_submit(ses, code[0], code[1], code[2]) for code in codes]
    # purify codes to store only src of codes
    for i, c in enumerate(codes):
        codes[i] = c[2]
    submissionIds = await asyncio.gather(*tasks)
    # prepare filters to validation later
    get_result_filiter = {}
    if filters != {}:
        for i in range(len(submissionIds)):
            if codes[i] in filters and "expireTime" in filters[codes[i]]:
                get_result_filiter.update(
                    {submissionIds[i]: filters[codes[i]]["expireTime"]})
    # get submission results
    result = await get_result(
        ses,
        submissionIds,
        submission_time_limit=get_result_filiter,
        MAX_TIMEOUT=max_time,
    )
    await ses.close()
    if code != "" or config != "":
        for _id, code in zip(submissionIds, codes):
            result[_id].update({"src": code})
    if config != "":
        result, all_pass = full_filter(result, filters)
        result.update({"passTest": all_pass and "wait_status" not in result})
        assert result["passTest"]
    with open(fname, "w") as f:
        f.write(json.dumps(result, indent=4))
