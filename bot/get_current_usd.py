'''
Функция получения курса USD to RUB от ЦБ РФ.
'''

import requests
from datetime import datetime


ANSWER = []


def usd_rate_check(old_list):
    s_date = old_list[0]
    if int(s_date) - int(str(datetime.now())[8:10:]) > 0:
        new_list = CBR_XML_Daily_Ru()
        return new_list
    return old_list


def CBR_XML_Daily_Ru(*_args_):
    url = ("https://www.cbr-xml-daily.ru/daily_json.js")
    
    response = requests.request("GET", url)
    
    data = response.json()

    s_date = data['Date']
    usd = data['Valute']['USD']['Value']

    ANSWER.append(s_date[8:10:])
    ANSWER.append(usd)

    return ANSWER



if __name__ == '__main__':
    print(CBR_XML_Daily_Ru())




