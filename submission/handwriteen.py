from . import submission
from .core_utils import seq_handwritten_grade , seq_handwritten_download
from cores import login
import logging
import click
@submission.command()
@click.argument("sid" , type=str)
@click.argument("score" , type=int)
def handwriteen_score(sid:str , score:int):
    '''
    try to modify someone's score
    '''
    sess = login.get_session("student1")
    if seq_handwritten_grade(sess , sid , score):
        logging.info("success update the handwritten grade")

@submission.command()
@click.argument("sid" , type=str)
@click.option("-u" , "--user" , "user" , default="first_admin" , help="the user to login as")
@click.option("--fname" , "filename" , default="something.pdf" , help="the name of download file")
def handwritten_download(sid:str , user:str , filename:str):
    '''
    download handwritten pdf
    '''
    sess = login.get_session(user)
    if seq_handwritten_download(sess , sid , filename):
        logging.info(f"successfully download as {filename}")
    else:
        logging.warning(f"failed to download file : {filename}")