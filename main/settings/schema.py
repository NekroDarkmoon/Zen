cogs: list = ["Leveling", "Logging", "Quests", "PlayChannels", "Reputation"]


tables:dict = {
  "settings": f"""
    serverId BIGINT PRIMARY KEY NOT NULL,
    ownerId BIGINT NOT NULL,
    prefix TEXT DEFAULT NULL,
    {",".join([f'{cog} BOOLEAN DEFAULT FALSE' for cog in cogs])},
    loggingChn BIGINT  
  """,

  "logger": """
    serverId BIGINT PRIMARY KEY NOT NULL,
    userId BIGINT NOT NULL,
    channelId BIGINT NOT NULL,
    lastMsg DATE NOT NULL
  """,

  # "logging": """
#     serverID BIGINT PRIMARY KEY REFERENCES logger(serverID),
#     userID BIGINT REFERENCES logger(userID),
#     channelId BIGINT REFERENCES logger(channelId),
#     time DATE DEFAULT CURRENT_DATE,
#     content TEXT
  # """,

  # "bookmarks": [],
  "quests": """
    serverId BIGINT PRIMARY KEY NOT NULL,
    userId BIGINT NOT NULL,
    questID INT NOT NULL,
    type TEXT,
    postedOn DATE DEFAULT CURRENT_DATE,
    msg TEXT
  """,

  "playchns": """
    serverId BIGINT PRIMARY KEY NOT NULL,
    userId BIGINT NOT NULL,
    map BOOLEAN DEFAULT FALSE    
  """
  ,

  # "pbp": [],

  "rep": """
    serverId BIGINT PRIMARY KEY NOT NULL,
    userId BIGINT NOT NULL,
    rep INT NOT NULL,
    lastGiven DATE DEFAULT CURRENT_DATE
  """,

  # "tags": [],

  "xp": """
    serverId BIGINT PRIMARY KEY NOT NULL,
    userId BIGINT NOT NULL,
    xp INT NOT NULL,
    level INT NOT NULL
  """,
}
