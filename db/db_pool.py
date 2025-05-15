import oracledb
from config import DB_USER, DB_PWD, DSN, WALLET_DIR, WALLET_PWD

db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = oracledb.create_pool(
            user=DB_USER,
            password=DB_PWD,
            dsn=DSN,
            min=2,
            max=10,
            increment=1,
            wallet_location=WALLET_DIR,
            wallet_password=WALLET_PWD
        )

def get_connection():
    global db_pool
    return db_pool.acquire()
