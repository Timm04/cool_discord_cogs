"""Provides functions for accessing S3 data and reading from database."""
import asyncio
import json
import os
import pkgutil
import sqlite3

import boto3

if not os.path.exists('data'):
    os.mkdir('data')
if not os.path.exists('data/server_data'):
    os.mkdir('data/server_data')
if not os.path.exists('cogs/config'):
    os.mkdir('cogs/config')
########################################
# S3 Functions

DEFAULT_BUCKET = pkgutil.get_data(__package__, "config/default_bucket.txt").decode()
s3_client = boto3.client('s3')


async def download_from_s3(local_path: str, remote_path: str, bucket=DEFAULT_BUCKET):
    def pull():
        print(f"Downloading file {remote_path}")
        s3_client.download_file(bucket, remote_path, local_path)
        return True

    loop = asyncio.get_running_loop()
    download_finished = await loop.run_in_executor(None, pull)
    return download_finished


async def list_files_from_s3(folder_path="", bucket=DEFAULT_BUCKET):
    def list_files():
        files_response = s3_client.list_objects(Bucket=bucket, Prefix=folder_path)
        files = []
        for result in files_response['Contents']:
            if "/" in result['Key'] and not result['Key'].endswith('/'):
                files.append(result['Key'].split("/")[1])
            else:
                files.append(result['Key'])

        return files

    loop = asyncio.get_running_loop()
    file_list = await loop.run_in_executor(None, list_files)
    return file_list


async def upload_to_s3(local_path: str, remote_path: str, bucket=DEFAULT_BUCKET):
    def push():
        print(f"Uploading file {local_path} to {remote_path}")
        s3_client.upload_file(local_path, bucket, remote_path)
        print(f"Finished uploading file {local_path} to {remote_path}")
        return True

    loop = asyncio.get_running_loop()
    upload_finished = await loop.run_in_executor(None, push)
    return upload_finished


async def delete_from_s3(remote_path: str, bucket=DEFAULT_BUCKET):
    def delete():
        print(f"Deleting {remote_path} from {bucket}.")
        s3_client.delete_object(Bucket=bucket, Key=remote_path)
        return True

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, delete)


########################################
# SQLite Functions
connection = sqlite3.connect("data/server_data/settings.db", check_same_thread=False)
cursor = connection.cursor()
operation_lock = asyncio.Lock()


async def create_table(table_name: str, columns: tuple):
    def create():
        result = cursor.execute(f"""SELECT name 
        FROM sqlite_master 
        WHERE name='{table_name}'""")

        if result.fetchone():
            # Table already exists.
            return
        columns_string = ", ".join(columns)
        with connection:
            print(f"Creating table {table_name} with the following columns: {columns_string}")
            cursor.execute(f"CREATE TABLE {table_name}({columns_string})")

    async with operation_lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, create)


async def verify_entry_guild(table: str, guild_id: int, kwargs=None):
    verify_existence_request = f"SELECT guild_id\n" \
                               f"FROM {table}\n" \
                               f"WHERE guild_id = '{guild_id}'"
    create_entry_request = f"INSERT INTO {table} (guild_id)\n" \
                           f"VALUES ('{guild_id}')"

    if kwargs:
        columns = ["guild_id"]
        columns.extend(kwargs.keys())
        values = kwargs.values()
        values = [f"'{json.dumps(value)}'" for value in values]
        values.insert(0, f"'{guild_id}'")
        columns_string = ", ".join(columns)
        values_string = ", ".join(values)
        create_entry_request = f"INSERT INTO {table} ({columns_string})\n" \
                               f"VALUES ({values_string})"
        for key, value in kwargs.items():
            verify_existence_request += f"\nAND {key} = '{json.dumps(value)}'"

    def verify():
        with connection:
            result = cursor.execute(verify_existence_request)
            result = result.fetchone()
            if not result:
                print(f"Creating entry in {table} for guild {guild_id} {f'with kwargs {kwargs}' if kwargs else ''}.")
                cursor.execute(create_entry_request)

    async with operation_lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, verify)


async def verify_entry_single(table: str, kwargs):
    verify_existence_request = str()
    columns_string = ", ".join(kwargs.keys())
    values_string = ", ".join(f"'{json.dumps(value)}'" for value in kwargs.values())
    create_entry_request = f"INSERT INTO {table} ({columns_string})\n" \
                           f"VALUES ({values_string})"

    for column_string, value in kwargs.items():
        if "WHERE" in verify_existence_request:
            verify_existence_request += f"\nAND {column_string} = '{json.dumps(value)}'"
        else:
            verify_existence_request = f"SELECT {column_string}\n" \
                                       f"FROM {table}\n" \
                                       f"WHERE {column_string} = '{json.dumps(value)}'"

    def verify():
        with connection:
            result = cursor.execute(verify_existence_request)
            result = result.fetchone()
            if not result:
                print(f"Creating entry in {table}  {f'with kwargs {kwargs}' if kwargs else ''}.")
                cursor.execute(create_entry_request)

    async with operation_lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, verify)


async def update_entry(table, column, value, guild_id=None, **kwargs):
    value_as_string = json.dumps(value).replace("'", "''")
    sq_lite_request_string = f"""UPDATE {table}\nSET {column} = '{value_as_string}'"""

    if guild_id:
        sq_lite_request_string = sq_lite_request_string + f"\nWHERE guild_id = '{guild_id}'"

    if kwargs:
        for kwargs_key, kwargs_value in kwargs.items():
            if "WHERE" in sq_lite_request_string:
                sq_lite_request_string = sq_lite_request_string + f"\nAND {kwargs_key} = '{json.dumps(kwargs_value)}'"
            else:
                sq_lite_request_string = sq_lite_request_string + f"\nWHERE {kwargs_key} = '{json.dumps(kwargs_value)}'"

    def update():
        with connection:
            print(f"Updating {column} for the guild {guild_id} with {value_as_string} "
                  f"{f'and kwargs {kwargs}' if kwargs else ''}")
            cursor.execute(sq_lite_request_string)

    if guild_id:
        await verify_entry_guild(table, guild_id, kwargs)
    else:
        await verify_entry_single(table, kwargs)
    async with operation_lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, update)


async def fetch_entry(table, column, guild_id=None, default_type=list, **kwargs):
    print(f"Performing query {table}:{column}:{guild_id}:{kwargs if kwargs else ''}")
    sq_lite_request_string = f"SELECT {column}\n" \
                             f"FROM {table}"

    if guild_id:
        sq_lite_request_string = sq_lite_request_string + f"\nWHERE guild_id = '{guild_id}'"

    if kwargs:
        for kwargs_key, kwargs_value in kwargs.items():
            if "WHERE" in sq_lite_request_string:
                sq_lite_request_string = sq_lite_request_string + f"\nAND {kwargs_key} = '{json.dumps(kwargs_value)}'"
            else:
                sq_lite_request_string = sq_lite_request_string + f"\nWHERE {kwargs_key} = '{json.dumps(kwargs_value)}'"

    def fetch():
        result = cursor.execute(sq_lite_request_string)
        result = result.fetchall()
        try:
            if not result[0][0]:
                return default_type()
        except (TypeError, IndexError):
            return default_type()
        if len(result) == 1:
            result = json.loads(result[0][0])
        else:
            result_list = []
            for data in result:
                result_list.append(json.loads(data[0]))
            result = result_list
        return result

    async with operation_lock:
        loop = asyncio.get_running_loop()
        entry = await loop.run_in_executor(None, fetch)
    print(f"Answering query {table}:{column}:{guild_id} with {entry}")
    return entry


async def delete_entry(table, guild_id, **kwargs):
    sq_lite_request_string = f"DELETE FROM {table}\n" \
                             f"WHERE guild_id = '{guild_id}'"

    if kwargs:
        for kwargs_key, kwargs_value in kwargs.items():
            sq_lite_request_string = sq_lite_request_string + f"\nAND {kwargs_key} = '{json.dumps(kwargs_value)}'"

    def delete():
        with connection:
            print(f"Deleting entry {guild_id} from {table} {'' if not kwargs else f'with kwargs {kwargs}'}")
            cursor.execute(sq_lite_request_string)

    async with operation_lock:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, delete)
