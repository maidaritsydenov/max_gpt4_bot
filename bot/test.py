import csv
from pathlib import Path
from datetime import datetime



cwd = Path.cwd()
path_to_users_file_linux = f'{cwd}/users/users.csv'
path_to_users_file_windows = f'{cwd}/users/users.csv'

users = [
    {
        "_id": 123,
        "username": None,
        "first_name": 'asd',
        "last_name": 'dsa',
        "last_interaction": datetime.now(),
        "n_used_tokens": 1000,
    },
    {
        "_id": 123456,
        "username": 'maidaritsydenov',
        "first_name": 'mai',
        "last_name": 'dari',
        "last_interaction": datetime.now(),
        "n_used_tokens": 5000,
             
    }]
user_list_csv = [['1', '123', '@None', 'asd', 'dsa', '2023-03-23 17:23', '1000'],
                 ['2', '123456', '@maidaritsydenov', 'mai', 'dari', '2023-03-23 17:23', '5000']]
user_list_csv = []
count = 1

header = ['Number', "ID", 'Username', 'First_name', 'Last_name', 'Last_interaction', 'N_used_tokens']

for user in users:
    user_attr = [f"{count}", f"{user['_id']}", f"@{user['username']}", f"{user['first_name']}", f"{user['last_name']}", f"{str(user['last_interaction'])[:16:]}", f"{user['n_used_tokens']}"]
    user_list_csv.append(user_attr)
    count += 1

print(user_list_csv)

with open(path_to_users_file_windows, 'w') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            writer.writerows(user_list_csv)

# print(len(users))
# print(users[1])

