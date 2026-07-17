import psycopg2

with open("Internal Database URL.txt", encoding="utf-8") as f:
    url = postgresql://tracker_oposiciones_db_user:RPCcOkf23eYjQtYnhHhMB0JuoGIVB3Zt@dpg-d97tsspkh4rs73bklbmg-a.frankfurt-postgres.render.com/tracker_oposiciones_db

conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute(
    "SELECT id, email, is_pro, stripe_customer_id, fecha_registro "
    "FROM usuarios ORDER BY fecha_registro DESC LIMIT 10;"
)
for fila in cur.fetchall():
    print(fila)
cur.close()
conn.close()