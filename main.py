import click
import logging
from submission import tester

logging.basicConfig(level=logging.DEBUG)


@click.group()
def command_entry():
    '''
    testing api for noj
    '''


if __name__ == "__main__":
    command_entry.add_command(tester.submission)
    command_entry()
