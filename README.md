# Zen

A discord bot to help manage TTRPG servers.

### Features
Zen includes the following cogs.

#### Bookmark
The bookmark cog enables the use of bookmarking messages in a server and having them be sent to your direct messages for later pursuing. Simply react to a message with :bookmark: and it'll be sent your direct messages.

*This functionality can be disabled in settings on a per server.*

#### Exandria
This Exandria cog has custom features pertaining to the Exandria discord server. 

#### Game
The game cog allows for users to create their own channels in a given category. These channels are hidden from all users by default and the creator of the channel can then add other users to the created channel. This creates a private space for them to play a game.

*This functionality can be disabled in settings on a per server.*

#### Hashtag
The hashtag cog allows moderators to set channels to require tags to be used. A tag is a word surrounded with square brackets that is placed at the start of a message. An example of such a message can be found below. If a message doesn't have the proper a warning is sent to the user to add tags to posts and the original post is deleted.

*This functionality can be disabled in settings on a per server.*
*This is a moderator only cog.*

#### Logger
The logger cog handles logging messages to a channel that's been designated as a logging channel. Information such as deleted messages, edited messages, changed nicknames, server joins, and server leaves are logged to this channel. **Do note that the bot doesn't store any of this information.**

*This functionality can be disabled in settings on a per server.*
*This is a moderator only cog.*

#### Meta
#### Mod
#### Owner
#### Rep
#### Settings
#### XP


### Running
1. Install python version 3.11 or higher.
2. Set up a venv `python -m venv .venv`
3. Install dependencies with `python -m pip install -U -r requirements.txt`
4. Configure settings file. A sample file is provided in `./main/settings/sample_config.py`. Edit it and rename it to `config.py`.
5. Create a database in PostgresSQL. Configure the database with the following commands. `CREATE ROLE Zen WITH LOGIN PASSWORD 'yourpw'; CREATE DATABASE Zen OWNER Zen; CREATE EXTENSION pg_trgm;`
6. Launch bot with `python launcher.py`


### Privacy Policy and Terms of Service
- No Personal data is stored.