import streamlit as st
import streamlit_authenticator as stauth
from streamlit_autorefresh import st_autorefresh
import sqlite3
import os
import yaml
from yaml.loader import SafeLoader
import time

db_path = "./chat_messages.sqlite3"

# Streamlit app configuration
st.set_page_config(
    page_title="Anonymous remarks",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items=None
)

count = st_autorefresh(interval=10000)


# Database setup
def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


# Insert a new message
def save_message(conn: sqlite3.Connection, content: str) -> None:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (content) VALUES (?)", (content,))
    conn.commit()


# Retrieve all messages
def get_messages(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT content, timestamp FROM messages ORDER BY id")
    return cursor.fetchall()


# Delete all messages
def clear_messages(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages")
    conn.commit()


# Check database file size
def is_db_size_exceeded(file_path: str, size_limit_mb: int = 1024) -> bool:
    assert os.path.exists(file_path)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    return file_size_mb > size_limit_mb


# Initialize database
connection = init_db()

# Load authenticator config
# This is bad practice as it exposes the hash in GitHub.
# This info should be stored in streamlit secrets.

with open('./config.yml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.authenticate.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
)

# Initialize session state for authentication and message refreshing
if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = None
    st.session_state["username"] = None
    st.session_state["name"] = None

if "clear_messages_trigger" not in st.session_state:
    st.session_state["clear_messages_trigger"] = False

if "last_refresh_time" not in st.session_state:
    st.session_state["last_refresh_time"] = time.time()

# Login form
if st.session_state["authentication_status"] is None:
    name, authentication_status, username = authenticator.login()
    if authentication_status:
        st.session_state["authentication_status"] = True
        st.session_state["username"] = username
        st.session_state["name"] = name
    elif authentication_status is False:
        st.error("Username/password is incorrect")
else:
    name = st.session_state["name"]
    username = st.session_state["username"]

# Main application
if st.session_state["authentication_status"]:
    st.title("Anonymous remarks 🎭")

    # Admin-specific functionality
    if username.lower() == "admin":
        if st.button("Clear all messages"):
            clear_messages(connection)
            st.success("All messages have been cleared.")
            st.session_state["clear_messages_trigger"] = True

    # Chat input
    user_message = st.chat_input("Type your message here...")

    # Check file size and save message if within limit
    if user_message:
        if is_db_size_exceeded(db_path):
            st.warning("Database size has exceeded 1 GB. New messages cannot be added.")
        else:
            save_message(connection, user_message)

    # Refresh messages if triggered or after a set time interval
    if (
        st.session_state["clear_messages_trigger"]
        or time.time() - st.session_state["last_refresh_time"] > 5
    ):
        st.session_state["clear_messages_trigger"] = False
        st.session_state["last_refresh_time"] = time.time()

    # Display all messages
    messages = get_messages(connection)
    for message_content, timestamp in messages:
        st.chat_message("user").markdown(f"**{message_content}**  \n*{timestamp}*")

elif st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
