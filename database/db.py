from peewee import Proxy

# Proxy экземпляр базы данных, инициализируется в database.init
# или в тестах через main_db.initialize(...)

db = Proxy()
