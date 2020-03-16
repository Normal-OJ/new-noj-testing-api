import click
import logging
import asyncio
import time
from cores import login
from . import submission
from .pressure_tester import submission
from .core_utils import seq_rejudge , async_rejudge , seq_get_status , async_get_status
@submission.command()
@click.option("-s", "--sid", "submission_id", type=str, default="", help="the submission id you want to submit , will generate one on runtime if not given")
@click.option("-c", "--count", "count", type=int, default=1, help="the time of testing rejudge")
@click.option("--seq", "sequential", type=bool, default=True, help="wheather to test it in specify order")
@click.option("--cfg", "config", type=click.File("r"), help="see github wiki for more detail")
@click.option("-d", "--delay", "delay", type=float, default=1.0, help="set the delay of checking up function(which will affect the accurrency of testing)")
@click.option("--maxTime", "max_time", type=float, default=3600, help="the maxium waiting time for waiting all the result(default is 3600 sec)")
@click.option("--fname", "fname", type=str, default="result.json", help="the filename of result(default is result.json)")
def rejudge(submission_id:str, count:int , sequential:bool, config , delay:float , max_time:float , fname:str):
    '''
    try to rejudge a specify submission
    '''
    assert submission_id ==  ""
    result = {}
    if sequential:
        sess = login.get_session()
        for i in range(count):
            send_rejudge([submission_id] , sequential)
            
            start_time = time.time()
            while True:
                status = seq_get_status(sess , submission_id)
                
                if status["status"] != -1:
                    result.update({f"{i}":status})
                    break
                if time.time() - start_time >= max_time:
                    result.update({"timeOut":True})
                    break
        if "timeOut" not in result:
            result.update({"timeOut":False})
    else:
        tars = []
        for i in range(count):
            tars.append(submission_id)
        
        send_rejudge(tars , sequential)
        
        sess = login.get_async_session()
        loop = asyncio.get_event_loop()
        while True:
            tasks = []
            for i in tars:
                tasks.append(asyncio.ensure_future(async_get_status(sess , i)))
            tasks = loop.run_until_complete(tasks)
            
            for i in len(tasks):
                r = tasks[i].result()
                if r["status"] != -1:
                    result.update({tars.pop(i):r})
                
def send_rejudge(submission_ids:list, sequential:bool):
    if sequential:
        sess = login.get_session()
        for i in submission_ids:
            seq_rejudge(sess , i)
    else:
        sess = login.get_async_session()
        loop = asyncio.get_event_loop()
        tasks = []
        for i in submission_ids:
            tasks.append(asyncio.ensure_future(async_rejudge(sess , i)))
        loop.run_until_complete(tasks)
