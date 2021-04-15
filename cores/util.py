import asyncio
from functools import wraps

__all__ = ('as_sync')


def as_sync(func):
    '''
    turn async function to sync function
    '''
    @wraps(func)
    def sync_func(*args, **ks):
        return asyncio.run(func(*args, **ks))

    return sync_func