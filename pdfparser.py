import fitz
import os
import sqlite3
import re
import pprint
from math import isclose
import constants


def parse_start():
    conn = sqlite3.connect(constants.DB_DIR)
    c = conn.cursor()

    # create database if doesn't exist
    if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='incidents'").fetchone() is None:
        schema = "CREATE TABLE incidents(\
        rms_id INTEGER PRIMARY KEY,\
        datetime VARCHAR(23) NOT NULL,\
        address VARCHAR(80),\
        type VARCHAR(80),\
        file VARCHAR(60) NOT NULL)"
        print("created db")
        c.execute(schema)

    it = os.scandir("data/franklin")
    for folder in it:
        if folder.is_dir():
            it_files = os.scandir(folder)
            for file in it_files:
                if file.is_dir():
                    print("Unexpected directory: " + file.path)
                else:
                    handleFile(file, conn)


def insert_db(conn: sqlite3.Connection, rms_num: str, datetime: str, address: str, inc_type: str, path: str):
    address = address.strip().upper()
    inc_type = inc_type.strip().upper()
    addr_pt = address.split(",")
    # make address more consistent
    addr_pt[0] = addr_pt[0].replace("@", " & ")
    addr_pt[0] = addr_pt[0].replace("/", " & ")

    # ignore apartment part of address
    address = ""
    for line in addr_pt:
        if line.find("APT") != -1:
            continue
        address += line.strip() + ", "

    address = address[:-2].replace("  ", " ")
    print("'{}'\t\t\t\t'{}'\t\t\t\t'{}'\t\t\t\t'{}'\t\t\t\t'{}'\t\t\t\t".format(rms_num, datetime, address, inc_type, path))

    c = conn.cursor()
    cmd = "SELECT COUNT(1) FROM incidents WHERE rms_id='{}'".format(rms_num)
    if c.execute(cmd).fetchone()[0] != 1:
        cmd = "INSERT INTO incidents(rms_id,datetime,address,type,file) VALUES (?, ?, ?, ?, ?);"
        c.execute(cmd, (rms_num, datetime, address, inc_type, path))
        conn.commit()


def handleFile(file: os.DirEntry, conn: sqlite3.Connection):
    with open(file, "rb") as fd:
        pdf_raw = fd.read()
        try:
            doc = fitz.open(stream=pdf_raw, filetype=".pdf")
        except RuntimeError:
            print("Error opening " + file.path)
            return

        # determine which version of the report it is
        if doc[0].getText("text").split("\n", maxsplit=1)[0].strip() == "Public Police Log":
            handleReportB(doc, conn, file.path)
        else:
            handleReportA(doc, conn, file.path)


def handleReportA(doc: fitz.Document, conn: sqlite3.Connection, path: str):
    pp = pprint.PrettyPrinter(indent=2)
    path_fixed = path.replace("\\", "/")
    for page in doc:
        page_dict = page.getText("dict")
        header = True
        for i, entry in enumerate(page_dict["blocks"]):
            if entry["bbox"][0] == 18.75:
                if header:
                    header = False
                    continue

                rms_num = ""
                address = ""
                inc_type = ""
                datetime = ""
                skip = False
                for field in entry["lines"]:
                    if field["spans"][0]["flags"] != 0:
                        skip = True
                        break

                    col = field["bbox"][0]
                    text = field["spans"][0]["text"].strip()
                    if isclose(col, 18.75, abs_tol=0.01):
                        if rms_num:
                            print("Error parsing: RMS double defined")
                        rms_num = text
                    elif isclose(col, 112.5, abs_tol=0.01):
                        if datetime:
                            print("Error parsing: date time double defined")
                        datetime = formatDatetime(text)
                    elif isclose(col, 231, abs_tol=0.01):
                        address += text + " "
                    elif isclose(col, 365.25, abs_tol=0.01):
                        inc_type += text + " "

                if not skip:
                    if not address:
                        # fix addresses with more than 3 lines are stored separetly
                        addr_box = page_dict["blocks"][i-1]
                        if isclose(addr_box["bbox"][0], 231.0, abs_tol=0.01):
                            for addr_line in addr_box["lines"]:
                                if isclose(addr_line["bbox"][0], 231.0, abs_tol=0.01):
                                    address += addr_line["spans"][0]["text"].strip() + " "

                    insert_db(conn, rms_num, datetime, address, inc_type, path_fixed)


def handleReportB(doc: fitz.Document, conn: sqlite3.Connection, path: str):
    path_fixed = path.replace("\\", "/")
    for page in doc:
        page_dict = page.getText("dict")
        header = True
        for entry in page_dict["blocks"]:
            if entry["bbox"][0] == 18:
                if header:
                    header = False
                    continue

                rms_num = ""
                address = ""
                inc_type = ""
                datetime = ""
                for field in entry["lines"]:
                    col = field["bbox"][0]
                    text = field["spans"][0]["text"].strip()
                    if col == 18:
                        if rms_num:
                            print("Error parsing: RMS double defined")
                        rms_num += text
                    elif col == 110.75:
                        if datetime:
                            print("Error parsing: datetime double defined")
                        datetime = formatDatetime(text)
                    elif col == 202.5:
                        address += text + " "
                    elif col == 381.5:
                        inc_type += text + " "

                insert_db(conn, rms_num, datetime, address, inc_type, path_fixed)


# Formats date time string from "mm/dd/yyy  HH:MM [AM/PM]" or
# "mm/dd/yyy  HH:MM" (24hr)
# to ISO8601 strings "YYYY-MM-DD HH:MM:SS.SSS"
def formatDatetime(timestamp: str):
    date = timestamp.split("  ")[0]
    time = timestamp.split("  ")[1]

    date_split = date.split("/")
    time_parts = re.findall("[0-9]{2}", time)
    hh = int(time_parts[0])

    if time[-2:] == "PM" and hh != 12:
        hh += 12
    elif time[-2:] == "AM" and hh == 12:
        hh = 0

    return "{}-{}-{} {:02d}:{}:00.000".format(date_split[2], date_split[1], date_split[0], hh, time_parts[1])