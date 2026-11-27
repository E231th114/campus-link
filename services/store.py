"""Small board storage. Row keys enforce unique reactions and time-slot limits."""
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient


class Local:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "board.sqlite"
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS rows (part TEXT, key TEXT, data TEXT, PRIMARY KEY(part,key))")

    def add(self, part, key, data):
        with closing(sqlite3.connect(self.db)) as db, db:
            result = db.execute("INSERT OR IGNORE INTO rows VALUES (?,?,?)", (part, key, json.dumps(data)))
            return bool(result.rowcount)

    def put(self, part, key, data):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("INSERT OR REPLACE INTO rows VALUES (?,?,?)", (part, key, json.dumps(data)))

    def rows(self, part):
        with closing(sqlite3.connect(self.db)) as db:
            return [dict(json.loads(data), RowKey=key) for key, data in
                    db.execute("SELECT key,data FROM rows WHERE part=?", (part,))]

    def delete(self, part, key):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("DELETE FROM rows WHERE part=? AND key=?", (part, key))

    def picture(self, key, data=None):
        file = self.root / (key + ".jpg")
        if data is None:
            return file.read_bytes()
        file.write_bytes(data)

    def delete_picture(self, key):
        file = self.root / (key + ".jpg")
        file.unlink(missing_ok=True)


class Azure:
    def __init__(self):
        table = os.getenv("AZURE_TABLE_NAME", "posts")
        container = os.getenv("AZURE_CONTAINER", "images")
        connection = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if connection:
            self.table = TableClient.from_connection_string(connection, table)
            self.blobs = ContainerClient.from_connection_string(connection, container)
        else:
            account = os.environ["AZURE_STORAGE_ACCOUNT"]
            identity = DefaultAzureCredential()
            self.table = TableClient(f"https://{account}.table.core.windows.net", table, identity)
            self.blobs = ContainerClient(f"https://{account}.blob.core.windows.net", container, identity)

    def add(self, part, key, data):
        try:
            self.table.create_entity(dict(data, PartitionKey=part, RowKey=key))
            return True
        except ResourceExistsError:
            return False

    def put(self, part, key, data):
        self.table.upsert_entity(dict(data, PartitionKey=part, RowKey=key))

    def rows(self, part):
        return list(self.table.query_entities("PartitionKey eq @part", parameters={"part": part}))

    def delete(self, part, key):
        try:
            self.table.delete_entity(partition_key=part, row_key=key)
        except ResourceNotFoundError:
            pass

    def picture(self, key, data=None):
        blob = self.blobs.get_blob_client(key + ".jpg")
        if data is None:
            try:
                return blob.download_blob().readall()
            except ResourceNotFoundError as exc:
                raise FileNotFoundError from exc
        blob.upload_blob(data)

    def delete_picture(self, key):
        try:
            self.blobs.delete_blob(key + ".jpg")
        except ResourceNotFoundError:
            pass
