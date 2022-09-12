"""Cog Description"""
import discord
import asyncio
import boto3
import shutil
from datetime import datetime
from discord.ext import commands
from discord.ext import tasks


class BackupData(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.s3_client = boto3.client('s3')

    async def cog_load(self):
        self.backup_data.start()

    async def cog_unload(self):
        self.backup_data.cancel()

    async def upload_backup(self, file_name):
        def push(file_name):
            print(f"Performing an upload of backup/{file_name}")
            self.s3_client.upload_file(f'backup/{file_name}', "v4-data-backups", f'{file_name}')
            return True

        loop = asyncio.get_running_loop()
        upload_success = await loop.run_in_executor(None, push, file_name)
        return upload_success

    async def create_backup(self):
        def create_data_zip():
            path_to_folder = f"data"
            date_string = datetime.utcnow().strftime("%Y-%m-%d")
            file_to_save = f"backup/data-{date_string}"
            shutil.make_archive(file_to_save, "zip", path_to_folder)
            file_name = f"data-{date_string}.zip"
            return file_name

        loop = asyncio.get_running_loop()
        file_name = await loop.run_in_executor(None, create_data_zip)
        return file_name

    @tasks.loop(hours=24)
    async def backup_data(self):
        await asyncio.sleep(3000)
        backup_file_name = await self.create_backup()
        upload_success = await self.upload_backup(backup_file_name)
        if upload_success:
            print(f"Uploaded backup: {backup_file_name}")



async def setup(bot):
    await bot.add_cog(BackupData(bot))
