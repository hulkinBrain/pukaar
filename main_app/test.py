import pytz
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from datetime import datetime
local_timezone = pytz.timezone('Asia/Kolkata')
from_time = datetime.now().astimezone(local_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
print((from_time - relativedelta(days=1)).strftime("%d %B %I:%M%p"), "-",
  datetime.now().astimezone(local_timezone).strftime("%d %B %I:%M%p"))
