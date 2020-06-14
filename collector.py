from requests_html import HTMLSession
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time
import random
import constants
import os


# converts month string to number
def month2int(month: str):
    month = month.lower()
    if month == "january":
        return 1
    elif month == "february":
        return 2
    elif month == "march":
        return 3
    elif month == "april":
        return 4
    elif month == "may":
        return 5
    elif month == "june":
        return 6
    elif month == "july":
        return 7
    elif month == "august":
        return 8
    elif month == "september":
        return 9
    elif month == "october":
        return 10
    elif month == "november":
        return 11
    elif month == "december":
        return 12
    else:
        print("invalid month: " + month)
        return -1


# Get pdf files from police website. If current date is supplied, then only downloads files more recent than
# current date. formate date in "yyyy-mm-dd" format
def download(currentDate: str = None):
    day = -1
    month = -1
    year = -1
    if currentDate:
        date_split = currentDate.split("-")
        if len(date_split) != 3:
            raise SyntaxError
        day = int(date_split[2])
        month = int(date_split[1])
        year = int(date_split[0])
        # TODO: check date format

    home_url = "https://www.franklinma.gov/police-department/pages/daily-press-logs-and-arrest-logs"

    session = HTMLSession()
    data = session.get(home_url).text
    soup = BeautifulSoup(data, features="lxml")

    # gets table with daily reports and arrest logs
    table = soup.find("div", class_="field field-name-body field-type-text-with-summary field-label-hidden").findAll("table")[1]
    reports = table.find("tr", class_="even").findNext("td").findAll("a")
    for month in reports:
        month_num = month2int(month.contents[0].split(" ")[0])
        year_num = month.contents[0].split(" ")[1]
        downloadHelper(month.get("href"), month_num, year_num, session)



def downloadHelper(month_url: str, month: int, year: int, session):
    data = session.get(month_url).text

    soup = BeautifulSoup(data, features="lxml")
    days = soup.find("div", class_="field field-name-body field-type-text-with-summary field-label-hidden").findAll("li")

    # create folder data/franklin/year/month/[filename]
    # path_dir = "data/franklin/{}-{}/".format(year, month)
    path_dir = os.path.join(constants.DB_DIR, "{}-{}".format(year, month))
    Path(path_dir).mkdir(exist_ok=True, parents=True)

    # download daily report
    for day in days:
        pdflink = day.find("a").get("href")
        path = path_dir + pdflink.split("/")[-1] + ".pdf"
        if not Path(path).exists():
            print("downloading " + pdflink + " to " + path)
            time.sleep(random.uniform(0.6, 1.1))
            try:
                pdf_raw = session.get(pdflink).content
            except requests.exceptions.ConnectionError:
                filename = pdflink.split("/")[-1]
                if filename.find(".pdf") == -1:
                    filename = filename + ".pdf"
                pdflink = "https://www.franklinma.gov/sites/franklinma/files/uploads/" + filename
                print("link failed, trying " + pdflink)
                try:
                    pdf_raw = session.get(pdflink).content
                except requests.exceptions.ConnectionError:
                    print("Failed. Continueing")
                    continue

            with open(path, "+wb") as fd:
                fd.write(pdf_raw)
        else:
            print(path + " already exists")


