import click
import logging
from submission import pressure_tester, rejudge , handwriteen

logging.basicConfig(level=logging.DEBUG)


@click.group()
def command_entry():
    '''
    testing api for noj
    '''


if __name__ == "__main__":
    command_entry.add_command(pressure_tester.submission)
    command_entry()
