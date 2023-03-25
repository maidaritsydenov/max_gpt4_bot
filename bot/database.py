from typing import Optional, Any

import pymongo
import uuid
from datetime import datetime

import config
from get_current_usd import usd_rate_check


class Database:
    def __init__(self):
        self.client = pymongo.MongoClient(config.mongodb_uri)
        self.db = self.client["chatgpt_telegram_bot"]

        self.user_collection = self.db["user"]
        self.dialog_collection = self.db["dialog"]

    def check_if_user_exists(self, user_id: int, raise_exception: bool = False):
        if self.user_collection.count_documents({"_id": user_id}) > 0:
            return True
        else:
            if raise_exception:
                raise ValueError(f"User {user_id} does not exist")
            else:
                return False
        
    def add_new_user(
        self,
        user_id: int,
        chat_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
    ):
        old_answer = [int(str(datetime.now())[8:10:]), 75.0]
        new_answer = usd_rate_check(old_answer)
        
        s_date = new_answer[0]
        usd_rate = new_answer[1]

        user_dict = {
            "_id": user_id,
            "chat_id": chat_id,

            "username": username,
            "first_name": first_name,
            "last_name": last_name,

            "last_interaction": datetime.now(),
            "first_seen": datetime.now(),
            
            "current_dialog_id": None,
            "current_chat_mode": "assistant",

            "n_used_tokens": 0,

            "s_date": s_date,
            "usd_rate": usd_rate,
            
            "token_limit": 10000
        }

        if not self.check_if_user_exists(user_id):
            self.user_collection.insert_one(user_dict)

    def start_new_dialog(self, user_id: int):
        self.check_if_user_exists(user_id, raise_exception=True)

        dialog_id = str(uuid.uuid4())
        dialog_dict = {
            "_id": dialog_id,
            "user_id": user_id,
            "chat_mode": self.get_user_attribute(user_id, "current_chat_mode"),
            "start_time": datetime.now(),
            "messages": []
        }

        # add new dialog
        self.dialog_collection.insert_one(dialog_dict)

        # update user's current dialog
        self.user_collection.update_one(
            {"_id": user_id},
            {"$set": {"current_dialog_id": dialog_id}}
        )

        return dialog_id

    def get_user_attribute(self, user_id: int, key: str):
        self.check_if_user_exists(user_id, raise_exception=True)
        user_dict = self.user_collection.find_one({"_id": user_id})

        if key not in user_dict:
            raise ValueError(f"User {user_id} does not have a value for {key}")

        return user_dict[key]

    def set_user_attribute(self, user_id: int, key: str, value: Any):
        self.check_if_user_exists(user_id, raise_exception=True)
        self.user_collection.update_one({"_id": user_id}, {"$set": {key: value}})

    def get_dialog_messages(self, user_id: int, dialog_id: Optional[str] = None):
        self.check_if_user_exists(user_id, raise_exception=True)

        if dialog_id is None:
            dialog_id = self.get_user_attribute(user_id, "current_dialog_id")

        dialog_dict = self.dialog_collection.find_one({"_id": dialog_id, "user_id": user_id})               
        return dialog_dict["messages"]

    def set_dialog_messages(self, user_id: int, dialog_messages: list, dialog_id: Optional[str] = None):
        self.check_if_user_exists(user_id, raise_exception=True)

        if dialog_id is None:
            dialog_id = self.get_user_attribute(user_id, "current_dialog_id")
        
        self.dialog_collection.update_one(
            {"_id": dialog_id, "user_id": user_id},
            {"$set": {"messages": dialog_messages}}
        )

    def get_users_list(self, user_id: int):
        self.check_if_user_exists(user_id, raise_exception=True)
        user_list_csv = []
        count = 1
        
        for user in self.user_collection.find():
            user_attr = [f"{count}", f"{user['_id']}", f"@{user['username']}", f"{user['first_name']}", f"{user['last_name']}", f"{str(user['last_interaction'])[:16:]}", f"{user['n_used_tokens']}"]
            user_list_csv.append(user_attr)
            count += 1
        return user_list_csv, count - 1
    
    
    def get_paid_subs_list(self, user_id: int, paid_subs_list: list):
        self.check_if_user_exists(user_id, raise_exception=True)
        paid_subs_list_csv = []
        count = 1
        
        for user in self.user_collection.find():
            if user['_id'] in paid_subs_list:
                user_attr = [f"{count}", f"{user['_id']}", f"@{user['username']}", f"{user['first_name']}", f"{user['last_name']}", f"{str(user['last_interaction'])[:16:]}", f"{user['n_used_tokens']}"]
                paid_subs_list_csv.append(user_attr)
                count += 1
        return paid_subs_list_csv, count - 1

    
    def update_balance_every_day(self):
        user_ids_list = []
        for user in self.user_collection.find():
            user_id = user['_id']
            if self.get_user_attribute(user_id, 'token_limit') < config.token_limit_for_users:
                self.set_user_attribute(user_id, 'token_limit', config.token_limit_for_users)
                user_ids_list.append(user_id)
        return user_ids_list
    
    def send_update_notice(self):
        user_ids_list = []
        for user in self.user_collection.find():
            if user["username"] != config.bot_username:
                user_ids_list.append(int(user['_id']))
        return user_ids_list
    
    
    def get_users_list(self, user_id: int):
        self.check_if_user_exists(user_id, raise_exception=True)
        user_list_csv = []
        count = 1
        
        for user in self.user_collection.find():
            user_attr = [f"{count}", f"{user['_id']}", f"@{user['username']}", f"{user['first_name']}", f"{user['last_name']}", f"{str(user['last_interaction'])[:16:]}", f"{user['n_used_tokens']}"]
            if user["username"] != config.bot_username:
                user_list_csv.append(user_attr)
                count += 1
        return user_list_csv, count - 1
    
    
    
    def delete_user(self, user_id: int):
        try:
            self.check_if_user_exists(user_id, raise_exception=True)
            username = self.get_user_attribute(user_id, "username")
            text = f"Пользователь с id: {user_id} username: {username} успешно удален из базы данных."
            user = self.user_collection.delete_one({"_id": user_id})
            return text
        except Exception as e:
            text = f"Пользователь с таким user_id не найден в базе данных. Ошибка {e}"
            return text
            
            
            
        