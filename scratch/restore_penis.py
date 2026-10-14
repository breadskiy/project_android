import psycopg
import subprocess
import os

print("Connecting to postgres...")
conn = psycopg.connect(
    dbname="postgres",
    user="postgres",
    password="psyebaaan",
    host="127.0.0.1",
    port=5432,
    autocommit=True
)
cur = conn.cursor()

print("Terminating connections to smart_supply_list...")
cur.execute("""
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = 'smart_supply_list' AND pid <> pg_backend_pid();
""")

print("Dropping existing smart_supply_list...")
cur.execute("DROP DATABASE IF EXISTS smart_supply_list;")

print("Creating fresh smart_supply_list...")
cur.execute("CREATE DATABASE smart_supply_list WITH ENCODING = 'UTF8';")
cur.close()
conn.close()

print("Recreated smart_supply_list successfully.")

cmd = [
    r"D:\postgreSQL\18\bin\pg_restore.exe",
    "-U", "postgres",
    "-h", "127.0.0.1",
    "-p", "5432",
    "-d", "smart_supply_list",
    "--no-owner",
    r"D:\project_android\penis.sql"
]

env = os.environ.copy()
env["PGPASSWORD"] = "psyebaaan"

print("Starting pg_restore from penis.sql...")
res = subprocess.run(cmd, env=env, capture_output=True, text=True)
print(f"pg_restore finished with code: {res.returncode}")
if res.stdout:
    print("Stdout:", res.stdout)
if res.stderr:
    print("Stderr (warnings/info):", res.stderr[:1000])

# Verify restored data
conn2 = psycopg.connect(
    dbname="smart_supply_list",
    user="postgres",
    password="psyebaaan",
    host="127.0.0.1",
    port=5432
)
cur2 = conn2.cursor()
cur2.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
tables = cur2.fetchall()
print(f"Restored {len(tables)} tables in public schema.")
for t in ["users", "products", "shopping_lists", "shopping_list_items"]:
    try:
        cur2.execute(f"SELECT count(*) FROM {t};")
        cnt = cur2.fetchone()[0]
        print(f"Table {t}: {cnt} rows")
    except Exception as e:
        print(f"Table {t} error: {e}")
cur2.close()
conn2.close()
