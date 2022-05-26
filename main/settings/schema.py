cogs: list = ["Leveling", "Logging", "Quests", "PlayChannels", "Reputation"]


tables: dict = {
    'settings': f'''
        server_id BIGINT PRIMARY KEY NOT NULL,
        owner_id BIGINT NOT NULL,
        prefix TEXT DEFAULT NULL,
        logging_channel BIGINT DEFAULT NULL,
        exception_role BIGINT DEFAULT NULL,
        enable_leveling BOOLEAN DEFAULT FALSE,
        enable_rep BOOLEAN DEFAULT FALSE,
        excluded_rep_channels BIGINT ARRAY NOT NULL DEFAULT array[]::bigint[],
        enable_game BOOLEAN DEFAULT FALSE,
        play_category BIGINT DEFAULT NULL,
        setup_completed BOOLEAN NOT NULL DEFAULT FALSE
    ''',

    'logger': f'''
        server_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        channel_id BIGINT NOT NULL,
        last_msg TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_gave_rep TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        msg_count BIGINT NOT NULL DEFAULT 0,
        PRIMARY KEY (server_id, user_id)
    ''',

    'game_channels': f'''
        server_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        channels BIGINT ARRAY DEFAULT NULL,
        PRIMARY KEY (server_id, user_id)
    ''',

    'reminders': f'''
        idx SERIAL PRIMARY KEY,
        expires TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event TEXT NOT NULL,
        extra JSON DEFAULT '{{}}'::jsonb
    ''',

    'rep': f'''
        server_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        rep INT NOT NULL,
        last_received TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        PRIMARY KEY (server_id, user_id)
    ''',

    'rep_log': f'''
        idx SERIAL PRIMARY KEY NOT NULL,
        server_id BIGINT NOT NULL,
        giver BIGINT NOT NULL,
        receiver BIGINT NOT NULL,
        amount INT NOT NULL,
        message_link TEXT NOT NULL,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ''',

    'rewards': f'''
        server_id BIGINT NOT NULL,
        role_id BIGINT NOT NULL,
        type TEXT NOT NULL,
        val INT NOT NULL,
        PRIMARY KEY (server_id, role_id, type)
    ''',

    'tags': f'''
        id SERIAL PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        server_id BIGINT NOT NULL,
        name TEXT NOT NULL,
        content TEXT NOT NULL,
        uses INT NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ''',

    'tag_lookup': f'''
        id SERIAL PRIMARY KEY,
        server_id BIGINT NOT NULL,
        owner_id BIGINT NOT NULL,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        tag_id INT NOT NULL REFERENCES tags(id) ON DELETE CASCADE
    ''',

    'threads': f'''
        server_id BIGINT NOT NULL PRIMARY KEY,
        channels BIGINT ARRAY DEFAULT NULL,
        threads BIGINT ARRAY DEFAULT NULL
    ''',

    'xp': f'''
        server_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        xp INT NOT NULL,
        level INT NOT NULL,
        last_xp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (server_id, user_id)
    ''',
}

indexes: list = [
    # Tags
]
