from datetime import datetime

now = datetime.now()
s_date = '2023-05-06T11:30:00.000+00:00'
s_date = s_date[:19].replace('T', ' ')
date_time_obj = datetime.strptime(s_date, '%Y-%m-%d %H:%M:%S')

timedelta = date_time_obj - now
print(timedelta.days < -1)

