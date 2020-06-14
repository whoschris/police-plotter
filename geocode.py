import sqlite3
import constants
import csv

# Create csv for upload to geocode.io for upload. Free tier allows 2500 lookups a day.
def create_upload_csv(file: str):
    conn = sqlite3.connect(constants.DB_DIR)
    c = conn.cursor()

    cmd = "SELECT DISTINCT address FROM incidents"
    records = c.execute(cmd).fetchall()
    with open(file, "x") as fd:
        fd.write("Address,Zip\n")  # header

        for rec in records:
            fd.write('"' + rec[0] + '",02038\n')


def parse_geocodio(file: str):
    data = []
    with open(file, "r") as fd:
        reader = csv.reader(fd)
        for line in reader:
            entry = {}
            if line[0] == "Address":
                continue
            entry["address"] = line[0].replace('"', '')
            entry["lat"] = line[2]
            entry["lon"] = line[3]
            entry["accuracy"] = line[4]
            entry["type"] = line[5]
            entry["zip"] = line[13]
            entry["address_geocoded"] = "{} {}, {} {}, {}".format(line[6], line[7], line[10], line[11], line[13])

            data.append(entry)

    conn = sqlite3.connect(constants.DB_DIR)
    c = conn.cursor()
    if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coords'").fetchone() is None:
        schema = "CREATE TABLE coords(\
                 address VARCHAR(80) PRIMARY KEY,\
                 lat VARCHAR(14) NOT NULL,\
                 lon VARCHAR(14) NOT NULL, \
                 flag INTEGER)"
        print("created coords table")
        c.execute(schema)

    cmd = "SELECT DISTINCT address FROM incidents"
    records = c.execute(cmd).fetchall()

    for line in data:
        # ignore and print warning if accuracy < 0.8, on highway, not in franklin,
        if float(line["accuracy"]) < 0.8:
            print("Warning: ignoring accuracy < 0.8\t\t" + line["address"])
            print("\tPredicted as " + line["address_geocoded"])
            continue
        elif line["address"].find("INTERSTATE") != -1 or line["address"].find("ROUTE 495") != -1:
            print("Warning: ignoring incidents along I-495\t\t" + line["address"])
            print("\tPredicted as " + line["address_geocoded"])
            continue
        elif line["zip"] != "02038":
            print("Warning: ignoring entries not in Franklin\t\t" + line["address"])
            print("\tPredicted as " + line["address_geocoded"])
            continue
        elif line["type"] == "street_center":
            print("Note: street center detected. Correct?\t\t" + line["address"])
            print("\tPredicted as " + line["address_geocoded"])
            # do not "continue"

        # override if highway interchange
        if line["address"].find("KING & RT 495") != -1:
            line["lat"] = "42.064812"
            line["lon"] = "-71.401153"
        elif line["address"].find("W CENTRAL & RT 495") != -1:
            line["lat"] = "42.090167"
            line["lon"] = "-71.427302"

        flag = 1 if line["type"] == "street_center" else 0
        c.execute("REPLACE INTO coords(address,lat,lon,flag) VALUES(?,?,?,?);", (line["address"],
                                                                                line["lat"],
                                                                                line["lon"],
                                                                                flag))
        conn.commit()



