'''
Функция получения курса USD to RUB от ЦБ РФ.
'''

import requests
from datetime import datetime


ANSWER = []

# s_date = '2023-04-17 11:20:00'
# s_date = datetime.strptime(s_date, '%Y-%m-%d %H:%M:%S')

# timedelta = s_date - datetime.now()
# print(timedelta.days)
# print(timedelta.days < -1)


def usd_rate_check(old_list, user_id):
    s_date = old_list[0]
    timedelta = s_date - datetime.now()
    if timedelta.days < -1:
        new_list = CBR_XML_Daily_Ru()
        return new_list
    return old_list


def CBR_XML_Daily_Ru(*_args_):
    url = ("https://www.cbr-xml-daily.ru/daily_json.js")
    
    response = requests.request("GET", url)
    
    data = response.json()

    s_date = data['Date'][:19].replace('T', ' ')
    usd = data['Valute']['USD']['Value']
    
    date_time_obj = datetime.strptime(s_date, '%Y-%m-%d %H:%M:%S')
    
    ANSWER.append(date_time_obj)
    ANSWER.append(usd)

    return ANSWER



if __name__ == '__main__':
    print(CBR_XML_Daily_Ru())




