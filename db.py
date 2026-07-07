import sqlite3

DB_PATH = "db/repolens.db"

def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    con = get_connection()
    with open("db/schema.sql") as file:
        schema_sql = file.read()
    con.executescript(schema_sql)
    con.commit()
    con.close()

if __name__ == "__main__":
    init_db()