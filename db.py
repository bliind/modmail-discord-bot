import sqlite3
import uuid

def open_db():
    return sqlite3.connect('modmail.db')

def create_ticket(user_id, user_name, channel_id, datestamp):
    try:
        conn = open_db()
        cur = conn.cursor()
        cur.execute('INSERT INTO ticket (id, user_id, user_name, channel_id, datestamp, active) VALUES (?, ?, ?, ?, ?, ?)', (str(uuid.uuid4()), user_id, user_name, channel_id, datestamp, 1))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print('Failed to create ticket:')
        print(e)
        return False

def delete_ticket(id: str):
    try:
        conn = open_db()
        cur = conn.cursor()
        cur.execute('DELETE FROM ticket WHERE id = ?', (id,))
        count = cur.rowcount
        conn.commit()
        conn.close()
        if count > 0:
            return True
        return False
    except Exception as e:
        print('Failed to delete ticket:')
        print(e)
        return False

def get_ticket(user_id):
    conn = open_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM ticket WHERE active = 1 AND user_id = ?', (user_id,))
    row = cur.fetchone()
    conn.close()

    try:
        return {
            "id":         row[0],
            "user_id":    row[1],
            "user_name":  row[2],
            "channel_id": row[3],
            "datestamp":  row[4],
            "active":     row[5]
        }
    except:
        return None

def get_ticket_by_channel(channel_id):
    conn = open_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM ticket WHERE channel_id = ?', (str(channel_id),))
    row = cur.fetchone()
    conn.close()

    try:
        return {
            "id":         row[0],
            "user_id":    row[1],
            "user_name":  row[2],
            "channel_id": row[3],
            "datestamp":  row[4],
            "active":     row[5]
        }
    except:
        return None

def close_ticket(id):
    try:
        conn = open_db()
        cur = conn.cursor()
        cur.execute('UPDATE ticket SET active = 0 WHERE id = ?', (id,))
        count = cur.rowcount
        conn.commit()
        conn.close()
        if count > 0:
            return True
        return False
    except Exception as e:
        print('Failed to close ticket:')
        print(e)
        return False


def get_tickets(user_id: int):
    conn = open_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM ticket WHERE user_id = ?', (user_id,))
    results = cur.fetchall()
    conn.close()

    out = []
    if results:
        for result in results:
            out.append({
                "id":         result[0],
                "user_id":    result[1],
                "user_name":  result[2],
                "channel_id": result[3],
                "datestamp":  result[4],
                "active":     result[5]
            })

    return out

def get_ticket_count(user_id: int):
    conn = open_db()
    cur = conn.cursor()
    cur.execute('SELECT id FROM ticket WHERE user_id = ?', (user_id,))
    results = cur.fetchall()
    conn.close()

    return len(results)

def add_block(user_id, user_name, moderator_id, reason):
    try:
        conn = open_db()
        cur = conn.cursor()
        cur.execute('INSERT INTO block (id, user_id, user_name, moderator_id, reason) VALUES (?, ?, ?, ?, ?)', (str(uuid.uuid4()), user_id, user_name, moderator_id, reason))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print('Failed to add block:')
        print(e)
        return False

def delete_block(user_id):
    try:
        conn = open_db()
        cur = conn.cursor()
        cur.execute('DELETE FROM block WHERE user_id = ?', (user_id,))
        count = cur.rowcount
        conn.commit()
        conn.close()
        if count > 0:
            return True
        return False
    except Exception as e:
        print('Failed to delete block:')
        print(e)
        return False
    
def list_blocks():
    conn = open_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM block')
    results = cur.fetchall()
    conn.close()

    out = []
    if results:
        for result in results:
            out.append({
                "id":            result[0],
                "user_id":       result[1],
                "user_name":     result[2],
                "moderator_id":  result[3],
                "reason":        result[4]
            })

    return out

def is_blocked(user_id):
    conn = open_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM block WHERE user_id = ?', (str(user_id),))
    row = cur.fetchone()
    conn.close()

    if row:
        return True
    return False
