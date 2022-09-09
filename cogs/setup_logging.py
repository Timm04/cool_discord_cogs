"""Cog Description"""
import discord
from discord.ext import commands
from discord.ext import tasks
import logging
import logging.handlers

class Logging(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        logger = logging.getLogger('discord')
        logger.setLevel(logging.INFO)
        logging.getLogger('discord.http').setLevel(logging.INFO)

        handler = logging.handlers.RotatingFileHandler(
            filename='data/logs/discord.log',
            encoding='utf-8',
            maxBytes=2 * 1024 * 1024,  # 2 MiB
            backupCount=10,  # Rotate through 5 files
        )
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        stream_handler = logging.StreamHandler()
        logger.addHandler(stream_handler)

async def setup(bot):
    await bot.add_cog(Logging(bot))
