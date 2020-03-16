from . import submission
from .core_utils import seq_handwritten_grade
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