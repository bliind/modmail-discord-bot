Is a modmail bot
but also has message reporting
and it's a little bit of spaghetti

but i'll break it out later™

```sql
CREATE TABLE ticket(
    id TEXT PRIMARY KEY NOT NULL,
    user_id INT,
    user_name INT,
    channel_id INT,
    datestamp INT,
    active INT
);

CREATE TABLE block(
    id TEXT PRIMARY KEY NOT NULL,
    user_id INT,
    user_name TEXT,
    moderator_id INT,
    reason TEXT
);
```
