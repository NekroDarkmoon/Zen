#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
import asyncio
import contextlib
import logging
import sys
from logging.handlers import RotatingFileHandler

import click

from main.cogs.utils.db import DB
from main.settings import config
from main.Zen import Zen

# Try Import
try:
    import uvloop  # type: ignore
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@click.group(invoke_without_command=True, options_metavar='[options]')
@click.pass_context
def main(ctx):
    """Starts the process of launching the bot."""
    if ctx.invoked_subcommand is None:
        with setup_logger():
            asyncio.run(run_bot())


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                      Setup Logging
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


class RemoveNoise(logging.Filter):  # pylint: disable=too-few-public-methods
    """Filter for logger"""

    def __init__(self):
        super().__init__(name='discord.state')

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelname == 'WARNING' and 'referencing an unknown' in record.msg:
            return False
        return True


@contextlib.contextmanager
def setup_logger():
    """Setup Logger as a Context Manager"""

    logger: logging.Logger = logging.getLogger()

    try:
        # __enter__
        max_bytes: int = 64 * 1024 * 1024
        logging.getLogger('discord').setLevel(logging.INFO)
        logging.getLogger('discord.http').setLevel(logging.WARNING)
        logging.getLogger('discord.state').addFilter(RemoveNoise())

        logger.setLevel(logging.INFO)
        handler: RotatingFileHandler = RotatingFileHandler(
            filename='.logs/Zen.log', encoding='utf_8', mode='w', maxBytes=max_bytes, backupCount=10
        )
        date_format = '%Y-%m-%d %H:%M:%S'
        formatter: logging.Formatter = logging.Formatter(
            '[{asctime}] [{levelname:<7}] {name}: {message}', date_format, style='{'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        yield

    finally:
        # __exit__
        handlers = logger.handlers[:]
        for handler in handlers:  # type: ignore
            handler.close()
            logger.removeHandler(handler)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Run Bot
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def run_bot():
    """Starts the process of running the bot"""
    log = logging.getLogger()

    # Create DB Connection
    try:
        pool = await DB.create_pool(config.uri)
    except Exception as e:  # pylint: disable=broad-except
        print(e)
        click.echo("Unable to setup/start Postgres. Exiting. ", file=sys.stderr)
        log.exception('Unable to setup/start Postgres. Exiting.')
        return

    if pool is None:
        raise RuntimeError('Unable to connect to db.')

    bot = Zen()
    bot.pool = pool
    await bot.start()


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Imports
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Init
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
if __name__ == '__main__':
    main()  # pylint: disable=no-value-for-parameter
