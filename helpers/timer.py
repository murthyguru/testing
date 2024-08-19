import calendar
from datetime import datetime, timedelta, date, time
import time as t # time name would clash with datetime's time
from typing import Callable, List, Union

from dateutil import parser

from helpers.common import printe


class _ProgressBar:
    """Prints a progress bar, best used if iterating over something many times
    and nothing else's being printed.
    """
    def __init__(self, target: int):
        self.target = target
        self.current = 0
        self._cpercent = 0

    def add(self, a: int = 1):
        self.current += a
        #print("Now %d/%d" % (self.current, self.target))
        npercent = self.current / self.target * 100
        #print("Current percent %d, new %d" % (self._cpercent, npercent))
        for _ in range(int(npercent) - int(self._cpercent)):
            self._cpercent += 1
            if self._cpercent % 10 == 0:
                print('|', end="", flush=True)
            elif self._cpercent % 2 == 0:
                print('.', end="", flush=True)


def time_function(funct: Callable, repeat: int = 20, **kwargs) -> dict:
    """Measures the execution time of a function, printing and returning info
    about execution time at the end.

    Any keyword arguments provided are passed directly to the function.

    Args:
        funct (Callable): Function to time
        repeat (int, optional): Number of times to call the function. Defaults
            to 20.

    Returns:
        dict: total, iterations, average
    """
    p = _ProgressBar(repeat)
    total_time = 0
    for _ in range(repeat):
        start = t.perf_counter()
        _ = funct(**kwargs)
        end = t.perf_counter()
        total_time += end - start
        p.add()

    print()
    print("Total time %s (average %s)" % (total_time, total_time / repeat))

    return {
        'total': total_time,
        'iterations': repeat,
        'average': total_time/repeat
    }


class JobScheduler:
    def __init__(self,
                days=0,
                days_of_week=None,
                dates=None,
                months=None,
                ref_time=None
                ):
        """This class helps with scheduling tasks that need to be repeated at
        some interval.

        If the task repeats, the next run date will be set to the same time
        as reference time, at some number of days in the future determined
        by a hierachy, where:
            a list of dates and months takes highest precedence
            list of days of the week are middle
            Else a number of days in the future

        An instance with all default values will not repeat, but could still be
        used to store a scheduled run time.

        Args:
            days (int, optional): Number of days between runs. Defaults to 0.
            days_of_week (list[int], optional): Days to run on, as integers
                (0 => Monday, 6 => Sunday). Note the difference between unix
                days. Defaults to None.
            dates (list[int], optional): Days of the month to run on. Defaults
                to None.
            months (list[int], optional): Months to run on. Defaults to None.
            ref_time (datetime, optional): The reference point to base the
                interval on. Defaults to
                datetime.now().replace(second=0, microsecond=0).
        """
        self.days = days
        self.days_of_week = days_of_week
        self.dates = dates
        self.months = months
        if isinstance(ref_time, str):
            try:
                self.ref_time = parser.parse(ref_time)
            except ValueError:
                printe("Unrecognized time format %s, expected ISO" % ref_time)
        elif isinstance(ref_time, datetime):
            self.ref_time = ref_time
        else:
            self.ref_time = datetime.now().replace(second=0, microsecond=0)

    @classmethod
    def from_datetime(cls, date_ref: Union[datetime, str], days=1):
        """Returns a JobScheduler with the initial due date set to the
        provided datetime, with optionally a number of days between runs
        defaulting to 1 (every day).

        Args:
            date_ref Union[datetime, str]: A date-like object (datetime or ISO
            formatted string) that will be the first due date.
            days (int, optional): Number of days between runs. Defaults to 1.

        Returns:
            JobScheduler: Instance of JobSchedular object.
        """
        return JobScheduler(days=days, ref_time=date_ref)

    def set_due_date(self, due_date: Union[datetime, date, str]=None) -> datetime:
        """Sets the reference date to the provided date. If no due date is
        provided, reschedules based on the current time and scheduling
        settings.

        Args:
            due_date (Union[datetime, date, str], optional): Date-like object to
                set the due date to If a date object is provided, the current
                due time will be preserved, otherwise it will be overwritten.
                Defaults to None - reschedules based on current settings.

        Returns:
            datetime: Newly set due date.
        """
        if isinstance(due_date, datetime):
            due_date = due_date.replace(second=0, microsecond=0)
            self.ref_time = due_date
        elif isinstance(due_date, date):
            self.ref_time = datetime.combine(due_date, self.ref_time.time())
        elif isinstance(due_date, str):
            self.ref_time = parser.parse(due_date)

        else:
            self.ref_time = self.next_due()

        return self.ref_time

    def set_due_time(self, due_time: Union[time, str]) -> datetime:
        """Sets the due time only for the current job schedule.

        Args:
            due_date (Union[datetime, date, str], optional): Date-like object to
                set the due date to If a date object is provided, the current
                due time will be preserved, otherwise it will be overwritten.
                Defaults to None - reschedules based on current settings.

        Returns:
            datetime: Newly set due date.
        """
        if isinstance(due_time, str):
            due_time = parser.parse(due_time).time()

        if isinstance(due_time, time):
            due_time = due_time.replace(second=0, microsecond=0)
            self.ref_time = datetime.combine(self.ref_time.date(), due_time)
            return self.ref_time

        raise ValueError("Not a recognized time format")

    def next_due(self, ref_time=None) -> datetime:
        """Determines the next due time, based on a reference time and the
        current settings.

        The reference time may be used to calculate a time in the future, e.g.
        providing a date that is a month after the due date will return a due
        date as though the current time were that future date.

        Args:
            ref_time (datetime, optional): Reference time from which to
                calculate the next due date. Defaults to None (uses Now).

        Returns:
            datetime: Next due date and time from reference time. If the job
                would not repeat after the reference time, returns None.
        """
        if ref_time is None:
            ref_time = datetime.now()

        if ref_time <= self.ref_time:
            return self.ref_time

        # # If it's after the due date but doesn't repeat, return None.
        elif not self.repeats:
            return None

        return self._next_due(ref_time, ref_time)

    def _next_due(self, calc_time, compare_time) -> datetime:
        """Internal wrapper for next due. If the calculated next due time
        ends up being before the reference time, we need to calculate again
        with the next day as a starting point (intervals run at most once per
        day), but be able to keep track of the original reference time to avoid
        infinite recursion loops.

        Args:
            calc_time (datetime): Time from which to calculate the next due date..
            compare_time (datetime): Originally requested calc_time.

        Returns:
            datetime: Next due time
        """
        next_due = datetime.combine(self.next_day(calc_time), self.ref_time.time())
        if next_due < compare_time:
            return self._next_due(calc_time + timedelta(days=1), compare_time)
        
        return next_due

    def repeat_none(self):
        """Sets the interval to not repeat."""
        self.days = None
        self.days_of_week = None
        self.dates = None
        self.months = None        

    def repeat_daily(self, days: int = 1):
        """Sets the interval to repeat every number of days.

        Args:
            days (int, optional): Number of days after which to repeat.
                Defaults to 1.
        """
        self.repeat_none()
        self.days = days

    def repeat_weekly(self, weeks: int = 1):
        """Sets the interval to repeat after a certain number of weeks.

        Args:
            weeks (int, optional): Number of weeks after which the interval
            will repeat. Defaults to 1.
        """
        self.repeat_none()
        self.days = weeks * 7

    def repeat_on_days_of_week(self, day_list: Union[int, List[int]]):
        """Sets the interval to repeat on certain days of the week. Each day
        of the week is specified by a datetime weekday() value, where 0 is
        Monday and 6 is Sunday.

        Args:
            day_list (Union[int, List[int]]): Days of the week to repeat.

        Raises:
            ValueError: If an invalid type is provided
            ValueError: If a day is not in the range 0-6
        """
        # Clear the current repeat days
        self.days_of_week = []
        self.dates = None
        self.months = None
        self.days = 0

        if isinstance(day_list, int):
            days = [day_list]
        elif isinstance(day_list, list):
            days = [int(x) for x in day_list]
        else:
            raise ValueError("Incompatible type of param day_list")

        for day in days:
            if not 0 <= day <= 6:
                raise ValueError("Invalid day of week.")
            self.days_of_week.append(day)

    def repeat_on_months(self, month_list: Union[int, List[int]]):
        """Sets the interval to repeat on certain months. If the dates are not
        also set, will set to repeat every date of the month.

        Args:
            month_list (Union[int, List[int]]): Months to repeat, where 1 => Jan
                and 12 => Dec

        Raises:
            ValueError: If an invalid type is provided
            ValueError: If a month is not in the range 1-12
        """
        self.days_of_week = None
        self.days = 0
        self.months = []

        if isinstance(month_list, int):
            months = [month_list]
        elif isinstance(month_list, list):
            months = [int(x) for x in month_list]
        else:
            raise ValueError("Incompatible type of param month_list")
        
        for month in months:
            if not 1 <= month <= 12:
                raise ValueError("Invalid month")
            self.months.append(month)
        if not self.dates:
            self.repeat_on_dates(list(range(1, 32)))

        if not self._validate_dates():
            raise ValueError("Invalid date/month setting - must be at least one"
                " valid date in the ranges.")
    
    def repeat_on_dates(self, date_list: Union[int, List[int]]):
        """Sets the interval to repeat on certain dates of the month. If months
        are not also set, will set to repeat every month.

        Args:
            date_list (Union[int, List[int]]): Dates to repeat.

        Raises:
            ValueError: If an invalid type is provided
            ValueError: If a date is not in the range 1-31
        """
        self.days_of_week = None
        self.days = 0
        self.dates = []

        if isinstance(date_list, int):
            dates = [date_list]
        elif isinstance(date_list, list):
            dates = [int(x) for x in date_list]
        else:
            raise ValueError("Incompatible type of param date_list")

        for day in dates:
            if not 1 <= day <= 31:
                raise ValueError("Invalid day of month")
            self.dates.append(day)
        if not self.months:
            self.repeat_on_months(list(range(1, 13)))

        if not self._validate_dates():
            raise ValueError("Invalid date/month setting - must be at least one"
                " valid date in the ranges.")

    def next_day(self, ref_time=None) -> date:
        """Returns the next date on which the interval will repeat.

        Args:
            ref_time (datetime, optional): Starting point from which to
                calculate the next date. If not provided, uses the starting date
                for the current object instance. Defaults to None.

        Returns:
            date: Next date that the interval will repeat.
        """

        if not ref_time:
            ref_time = self.ref_time

        if self.months and self.dates:
            next_month = get_closest(self.months, ref_time.month)

            # Filter out the days that are not in the range for this month/year
            valid_days = [x for x in self.dates
                if x <= calendar.monthrange(ref_time.year, next_month)[1]]

            # If there are no valid days, try again with the next month
            while not valid_days:
                next_month = get_closest(self.months, next_month + 1)
                valid_days = [x for x in self.dates
                    if x <= calendar.monthrange(ref_time.year, next_month)[1]]

            next_day = get_closest(valid_days, ref_time.day)

            test_date = date(ref_time.year, next_month, next_day)

            if test_date < ref_time.date():
                return self.next_day(ref_time + timedelta(days=1))

            else:
                return test_date

        elif self.days_of_week is not None:
            next_date = get_closest(self.days_of_week, ref_time.weekday())
            days_to_go = (next_date - ref_time.weekday()) % 7
            td = timedelta(days=days_to_go)
            
            return ref_time.date() + td

        elif self.days:
            date_diff = (ref_time.date() - self.ref_time.date()).days
            if date_diff <= 0:
                return self.ref_time.date()
            
            if date_diff % self.days == 0:
                return self.ref_time + timedelta(days=date_diff)
            else:
                date_diff = ((date_diff // self.days) + 1) * self.days
                return self.ref_time.date() + timedelta(days = date_diff)

        else:
            return None

    def to_dict(self) -> dict:
        """Returns a JSON serializable dictionary representation of itself.

        Returns:
            dict: JobScheduler as a dictionary.
        """
        try:
            ref_time = self.ref_time.isoformat()
        except AttributeError:
            ref_time = None
        as_dict= {
            "ref_time": ref_time,
            "days": self.days,
            "dates": self.dates,
            "days_of_week": self.days_of_week,
            "months": self.months
        }

        return as_dict

    def _validate_dates(self) -> bool:
        """Attempts to catch certain edge cases when setting to repeat on dates
        of the year, e.g. setting month to 2 and date to 30 won't ever match 
        a valid date. If at least one date is a valid date on a non-leap year,
        returns True, otherwise returns false.

        Returns:
            bool: True if at least one date is a valid date on a non-leap year,
                else False.
        """
        NON_LEAPYEAR = 2021
        for month in self.months:
            for day in self.dates:
                try:
                    _ = datetime(NON_LEAPYEAR, month, day)
                    return True
                except ValueError:
                    pass
        
        return False

    @property
    def repeats(self) -> bool:
        """Returns True if the interval repeats

        Returns:
            bool: True if the interval repeats.
        """
        if (self.days or self.days_of_week is not None or self.dates
            or self.months):
            return True

        return False

    @property
    def scheduled_time(self) -> time:
        return self.ref_time.time()


def python_weekday_to_unix(unix_days: List[int]) -> list:
    """Python weekdays use Monday as 0 and Sunday as 6. This converts a list
    of python weekdays into unix-like, so that Monday is 1 and Sunday is 0.

    Args:
        unix_days (List[int]): [description]

    Returns:
        list: [description]
    """
    return [(x + 1) % 7 for x in unix_days]


def unix_weekday_to_python(unix_days: List[int]) -> list:
    return [(x -1) % 7 for x in unix_days]


def get_closest(num_list: List[int], ref) -> int:
    """Returns the closest value that's greater than or equal to ref, or the
    smallest value in the list.

    Example:
        get_closest([5, 15, 30, 45], 35) -> 45
        get_closest([5, 15, 30, 45], 46) -> 5

    Args:
        num_list (list): List of numbers to find the next largest
        ref (int): Number reference point

    Returns:
        int: Next greatest number in the list
    """
    if not isinstance(num_list, list):
        if isinstance(num_list, int):
            return num_list
        else:
            raise AttributeError("Number list must be a list of numbers.")
    
    num_list.sort()
    for i in num_list:
        if i >= ref:
            return i

    return num_list[0]
