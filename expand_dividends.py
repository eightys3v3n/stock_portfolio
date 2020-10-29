import csv
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime, timedelta
from math import ceil
import logging
import unittest
import sys

DATE_FORMAT = "%Y-%m-%d"
# Dividend is the quarterly percent return.
FIELDS = ['date', 'dividend']


class Dividend:
    def __init__(self, date, dividend=None):
        if isinstance(date, str):
            try:
                self.date = datetime.strptime(date, DATE_FORMAT)
            except ValueError as e:
                logging.error("Date doesn't match pattern '{}': '{}'".format(DATE_FORMAT, date))
                raise e
        else:
            self.date = date
            
        self.end_date = None
        if isinstance(dividend, str):
            self.dividend = float(dividend)
        else:
            self.dividend = dividend
        
    def __repr__(self):
        return (self.date, self.dividend).__str__()

    def __eq__(self, o):
        if not isinstance(o, Dividend): return False
        if self.date != o.date: return False
        if self.dividend != o.dividend: return False
        return True


def csv_file(path, fields=None):
    f = open(path, 'r')
    reader = csv.DictReader(f, fieldnames=fields)
    for row in reader:
        yield row


def read_src_file(path):
    dividends = []
    csv = csv_file(path, fields=FIELDS)
    csv.__next__() # Skip the CSV header because Yahoo always exports with a header.
    
    for div in csv:
        dividends.append(Dividend(**div))
    dividends.sort(key=lambda x:x.date)
    return dividends


def last_dividend_before(dividends, date):
    """Returns the last dividend that happened before the specified date."""
    dividends = sorted(dividends, key=lambda x:x.date)
    for i, d in enumerate(dividends):
        if d.date > date:
            return dividends[i-1]


def avg_days_between(dividends):
    """Returns the average number of days between the dividend payments present in the input array."""
    dividends = sorted(dividends, key=lambda x:x.date)
    s = 0
    last_div = None
    for i, div in enumerate(dividends):
        if last_div is None:
            last_div = div
            continue
        
        days_between = div.date - last_div.date
        days_between = days_between.days
        s += days_between
        last_div = dividends[i]
    avg = s / (len(dividends)-1)
    return avg
        

def daily_dividends(dividends, predict_future_dividend=True):
    """Given dividend payment amounts and their dates, generate a list of daily payment amounts and dates.
    
    Optional keyword arguments:
        predict_future_dividend default=True: Whether or not to predict when the next dividend payment will occur
                                              and to generate the daily dividends until that future date.
    """
    dividends.sort(key=lambda x:x.date)
    range_of_dates = (min(dividends, key=lambda x:x.date).date, max(dividends, key=lambda x:x.date).date+timedelta(days=1))
    num_dates = range_of_dates[1] - range_of_dates[0]
    num_dates = num_dates.days

    assert range_of_dates[0] == dividends[0].date
    assert range_of_dates[1] == dividends[-1].date + timedelta(days=1)
    
    days = []
    for i, div in enumerate(dividends):
        if i == 0: continue
        last_div = dividends[i-1]
        
        days_between = (div.date - last_div.date).days
        for d in range(days_between):
            days.append(Dividend(last_div.date + timedelta(days=d), last_div.dividend / days_between))

    if predict_future_dividend:
        days_between = ceil(avg_days_between(dividends))
        for d in range(days_between):
            days.append(Dividend(dividends[-1].date + timedelta(days=d), dividends[-1].dividend / days_between))
        
    return days


def write_csv_file(path, dividends):
    with open(path, 'w', newline='') as csvfile:
        w = csv.writer(csvfile, delimiter=',')
        w.writerow(['Date', 'Dividend'])
        for d in dividends:
            w.writerow([d.date.strftime(DATE_FORMAT), d.dividend])
    

def main():
    logging.basicConfig(level=logging.DEBUG)
    
    parser = ArgumentParser(prog="Dividend History Expander", description='Expand a list of dividend payment dates and payment percents to a list of every day and the dividend payment for that day')
    parser.add_argument('--src', help="CSV file from Yahoo containing the dividend payment dates")
    parser.add_argument('--dst', help="CSV file to write the daily dividends into")
    parser.add_argument('--test', action="store_true", help="Run unit tests")
    args = parser.parse_args()

    if args.test:
        sys.argv.remove('--test')
        unittest.main()

    src = Path(args.src)
    if not src.exists():
        logging.error("Dividend source file doesn't exist: '{}'".format(src))
        return 1
    
    dividends = read_src_file(src)
    dividend_days = daily_dividends(dividends)
    write_csv_file(args.dst, dividend_days)


class TestExpander(unittest.TestCase):
    def test_last_dividend_before(self):
        inp = ([Dividend("2020-10-18"),
                Dividend("2020-10-20"),
                Dividend("2020-10-22")],
               datetime(2020, 10, 21))
        corr = Dividend("2020-10-20")
        ret = last_dividend_before(*inp)
        self.assertEqual(corr, ret)

    def test_avg_days_between(self):
        inp = [Dividend("2020-10-10"),
               Dividend("2020-09-10"),
               Dividend("2020-08-11")]
        corr = 30
        ret = avg_days_between(inp)
        self.assertEqual(corr, ret)

    def test_daily_dividends(self):
        inp = [Dividend("2020-10-10", '.3'),
               Dividend("2020-09-10", '.3'),
               Dividend("2020-08-11", '.3')]
        corr = []
        # 90 because two months of known dividends and one month of predicted dividends.
        # So it should have the dividend amounts for every day of 2020-08-11 to 2020-11-09
        # We divide the dividend rate by the days between payments to get the daily rate, 0.3/30=0.01
        for d in range(90):
            corr.append(Dividend(datetime(2020,8,11)+timedelta(days=d), '0.01'))
        ret = daily_dividends(inp)
        # for p in corr: print(p)
        # print("---------")
        # for p in ret: print(p)
        self.assertCountEqual(corr, ret)
        

if __name__ == '__main__':
    main()
