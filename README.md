***Telegram Bot: Educational Video Search System***

This repository contains the code for a Telegram bot developed as a part of the project "Розробка системи для пошуку навчальних відео з обраної теми" (Development of a System for Searching Educational Videos on a Selected Topic).


**Features**

Search YouTube Videos: Users can search for videos on YouTube by providing a query.

Personal Collections: Save videos into custom collections for later viewing.

Favorites: Automatically maintains a default "Favorites" collection.

View Collections: View videos saved in your collections with pagination.

Delete Collections and Videos: Manage collections and remove videos as needed.

User Persistence: Stores user and collection data in a PostgreSQL database.


**Technologies Used**

Python: Programming language for bot implementation.

Telegram Bot API: Interaction with Telegram.

YouTube Data API v3: Video search functionality.

PostgreSQL: Database for storing user and collection data.

Asyncio: Asynchronous handling of bot commands.


**Requirements**

Python 3.8+

PostgreSQL

API keys for:

Telegram Bot API

YouTube Data API v3


**Setup**

*1. Clone the Repository*

git clone https://github.com/yourusername/yourrepository.git
cd yourrepository

*2. Install Dependencies*

pip install python-telegram-bot;
pip install psycopg2;
pip install requests.
pip install googleapiclient


*3. Configure Database*

Set up a PostgreSQL database using your parameters in the code

Database Name: [your_db_name]

User: [your_user]

Password: [your_pass]

Host: localhost (or any other)

Port: 5432

Use the provided SQL scripts to initialize the database schema:

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE collections (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    youtube_id VARCHAR(50) NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE collection_videos (
    id SERIAL PRIMARY KEY,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, video_id)
);



*4. Set API Keys*

Replace placeholders in the code with your actual API keys:

Your YouTube Data API v3 key.

Telegram bot token in the main() function.

*5. Run the Bot*

python Komelkov.py (rename if you want to)


**Usage**

*Start the Bot*

Send the /start command to initialize the bot.

*Search Videos*

Use /search and then type your query to search for videos on YouTube.

*Create Collections*

Use /create_collection <collection_name> to create a new collection.

*View Collections*

Use /my_collections to see your collections and manage them.

*Add to Collection*

When videos are displayed, click the button to add them to a collection.

*Manage Collections*

View or delete collections and their videos through interactive buttons provided by the bot.

*Project Timeline*

Start Date: December 2, 2025

End Date: December 28, 2025

Contact

For questions or feedback, feel free to reach out to the repository owner.
