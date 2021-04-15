from . import submission
from .core_utils import seq_handwritten_grade, seq_handwritten_download, seq_submit
from cores import login
import logging
import click
import os


@submission.command()
@click.option("-u",
              "--user",
              "user",
              type=str,
              default="first_admin",
              help="the user to login as")
@click.argument("sid", type=str)
@click.argument("score", type=int)
def handwritten_score(user: str, sid: str, score: int):
    '''
    try to modify someone's score
    '''
    sess = login.get_session("student1")
    if seq_handwritten_grade(sess, sid, score):
        logging.info("success update the handwritten grade")


@submission.command()
@click.argument("sid", type=str)
@click.option("-u",
              "--user",
              "user",
              type=str,
              default="first_admin",
              help="the user to login as")
@click.option("--fname",
              "filename",
              type=str,
              default="something.pdf",
              help="the name of download file")
@click.option("-c",
              "--comment",
              "comment",
              type=bool,
              default=False,
              help="download comment(default False)")
def handwritten_download(comment: bool, sid: str, user: str, filename: str):
    '''
    download handwritten pdfs
    '''
    sess = login.get_session(user)
    if seq_handwritten_download(sess, sid, filename):
        logging.info(f"successfully download as {filename}")
    else:
        logging.warning(f"failed to download file : {filename}")

    if comment:
        filename, ext = os.path.splitext(filename)
        filename += "_comment"

        if seq_handwritten_download(sess, sid, filename + ext, 1):
            logging.info(f"successfully download as {filename}")
        else:
            logging.warning(f"failed to download file : {filename}")
