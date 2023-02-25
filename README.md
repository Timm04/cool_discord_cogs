A collection of extensions ('cogs') for discord.py.

# Cog Overview

## anime_search.py

Provides access to a database of Japanese video examples stored in Amazon S3. Search is implemented with groonga.

## assignable_roles.py

Provides commands that let users assign and unassign roles to themselves and command that let admins add and remove
roles to the list of self-assignable roles.

## auto_receive.py

Lets admins set up connections between roles which should be automatically distributed if another role is present.
Useful if rewards or channel access is tied to a role, and it can be unlocked by getting another role.

## backup.py

Regularly create a backup of the `data` folder and upload it to S3.

## bump.py

Bump reminders for Dissoku and Disboard. Can be expanded to include more bots.

## channel_clearer.py

Lets admins set up a task that regularly clears a channels content.

## config.py

Provides a few utility functions for bot owners such as reloading cogs and syncing commands.

## data_management.py

Handles uploads to S3 and writing/reading from the SQLite databank.

## error_catcher.py

Handles a few command errors.

## gpt_3_cog.py

Lets discord users interact with OpenAIs GPT3 API in the form of a chatbot. The bot is capable of reading the chat
history.

## join_and_leave.py

Sets up join and leave messages with optional file upload.

## levelup.py

Implements a framework for a rank system with the kotoba bot.
Each rank is represented by a corresponding quiz which has to be passed to get the rank.

## logging_setup.py

Sets logging settings. Also sends a message to the bot owner when an error is written to the log file.

## moderation.py

Implements delete, purge and pin context menus for moderators.

## notable_posts.py

Keeps track of posts that get a lot of reactions and reposts them in a nice embed in a designated channel.

## polling.py

Full polling solution with views that are persistent through restarts of the bot.

## quiz_cage.py

Lets admins give users a 'punishment' role until another role is attained. Useful with `levelup.py`.

## rank_saver.py

Saves user ranks and optionally restores them on rejoin.

## state_saver.py

Saves channels, permissions and a lot of other data about a server in a pickled file and lets admins restore servers
using those files.

## temporary_vc.py

Lets users create temporary voice channels that get cleared on rejoin.

## user_name_record.py

Saves the usernames of all known users. If a user is unknown it fetches the username. Useful to also have access
to usernames of users who left the server.

WARNING: For a lot of data involving guilds such as channel and role names, names are used instead of unique IDs.
This is done for the purpose of being able to easily copy-paste settings across guilds, but has the disadvantage of
breaking settings if things are renamed. If moving setting between servers is not intended, it is
recommended to use unique IDs.