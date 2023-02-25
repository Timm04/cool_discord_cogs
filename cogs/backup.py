"""Backup data files to S3"""
import asyncio
import datetime
import os
import shutil
from datetime import datetime

from discord.ext import commands
from discord.ext import tasks

from . import data_management

if not os.path.exists('backup'):
    os.mkdir('backup')


async def clear_redundant_files_from_s3():
    """Keep only one file per month and all files from the current month."""
    file_list = await data_management.list_files_from_s3()
    now = datetime.utcnow()
    current_month_string = now.strftime("%Y-%m")
    files_to_keep = [file for file in file_list if current_month_string in file or file.endswith("01.zip")]
    for file in file_list:
        if file not in files_to_keep:
            await data_management.delete_from_s3(file)


async def create_data_backup():
    def create_data_zip():
        path_to_folder = f"data"
        date_string = datetime.utcnow().strftime("%Y-%m-%d")
        file_to_save = f"backup/data-{date_string}"
        print(f"Creating backup for {date_string}")
        shutil.make_archive(file_to_save, "zip", path_to_folder)
        file_name = f"data-{date_string}.zip"
        return file_name

    loop = asyncio.get_running_loop()
    backup_file_name = await loop.run_in_executor(None, create_data_zip)
    return backup_file_name


async def clear_other_backup_files(current_back_file_name: str):
    for file_name in os.listdir("backup"):
        if file_name != current_back_file_name:
            os.remove(file_name)


class BackupData(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.backup_routine.start()

    async def cog_unload(self):
        self.backup_routine.cancel()

    @tasks.loop(hours=24)
    async def backup_routine(self):
        await asyncio.sleep(3000)
        await clear_redundant_files_from_s3()
        back_up_file_name = await create_data_backup()
        await data_management.upload_to_s3(f"backup/{back_up_file_name}", back_up_file_name)
        await clear_other_backup_files(back_up_file_name)


async def setup(bot):
    await bot.add_cog(BackupData(bot))
