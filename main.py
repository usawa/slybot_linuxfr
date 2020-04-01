#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib3
import xml.dom.minidom
import time
import html
import re
import random
import sqlite3
import dictons
from sqlite3 import Error


http = 0
previous_id = 0
last_id = 0

sql_create_tribune_table = """ CREATE TABLE IF NOT EXISTS tribune (
                                        id integer PRIMARY KEY,
                                        timer int NOT NULL, 
                                        info text NOT NULL,
                                        login text NOT NULL,
                                        message text NOT NULL
                                    ); """

sql_create_tribune_timer_index = """ CREATE INDEX IF NOT EXISTS idx_timer 
                                        ON tribune(timer); """

sql_create_tribune_login_index = """ CREATE INDEX IF NOT EXISTS idx_login 
                                        ON tribune(login); """

sql_select_posts = """ SELECT * from tribune where id>? and id<=? ; """

sql_select_random_posts = """ SELECT message from tribune where id!=? ORDER BY RANDOM() LIMIT 1; """

conjonctions = ["mais", "ou", "et", "donc", "or", "ni", "car"]

Prefix = ["Ah non", "Ah oui", "Certes", "En effet", "D'accord", "Non", "Oui", "Ah bon", "pourquoi", "Tu crois",
    "Ok", "Pas certain", "Sûrement", "Bien sûr", "Pas d'accord", "Ah ouais", "Pt'être bien", "Tu veux rire",
    "C'est certain", "Drôle", "Mais non", "Mais oui", "J'avoue", "Je plussoie", "Tes sûr"
]

def create_connection(db_file):
    global conn
    
    """ create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
 
    return conn

def sql_create(conn, create_table_sql):
    """ create a table from the create_table_sql statement
    :param conn: Connection object
    :param create_table_sql: a CREATE TABLE statement
    :return:
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e) 

def sql_insert(conn, tribune_id, timer, login, info, message):
    """
    Create a new task
    :param conn:
    :param task:
    :return:
    """

    # timer YYYYMMDDHHMMSS
    #       01234567890123
    year = timer[0:4]
    month = timer[4:6]
    day = timer[6:8]
    hour = timer[8:10]
    minutes = timer[10:12]
    seconds = timer[12:14]

    time_format = year+"-"+month+"-"+day+" "+hour+":"+minutes+":"+seconds

    sql = """INSERT OR REPLACE INTO tribune(id, timer, login, info, message)
              VALUES( ?, strftime('%s',?), ?, ?, ?); """

    values = (tribune_id, time_format, login, info, message )
    try:
        cur = conn.cursor()
        cur.execute(sql, values)
        conn.commit()
    except sqlite3.Error as error:
        print("Failed to insert Python variable into sqlite table", error)
    
    return cur.lastrowid

def get_board(url):
    global http
 #   pprint.pprint(http)
    if not http:
        http = urllib3.PoolManager()
    
    r = http.request('GET', url, timeout=3)

    return(r)

# parse XML result and store content in database
def parse_and_store_tribune(conn, data):
    global last_id
    global previous_id

    tribune = xml.dom.minidom.parseString(data)
  
    posts=tribune.getElementsByTagName("post")

    count = False

    previous_id = last_id 

    for post in posts:

        timer = post.getAttribute('time')
        tribune_id = post.getAttribute('id')

        if count is False:
            last_id = tribune_id

        count = True

        info = post.getElementsByTagName('info')[0].firstChild.data
        message = post.getElementsByTagName('message')[0].firstChild.data
        login  = post.getElementsByTagName('login')[0].firstChild.data

        sql_insert(conn, tribune_id, timer, login, info, message)

# Explose a message in multiple lines
def explode_message(txt):
    txt = txt.replace("!", ".")
    txt = txt.replace("?", ".")
    txt = txt.replace(";", ".")
    txt = txt.replace(",", ".")
    
    txt_list = []

    for string in txt.split("."):
        if (string != ""):
            txt_list.append(string.strip())

    return(txt_list)

def clean_message(txt):
    txt = re.sub('<.*?>','',txt)
    txt = re.sub(r'([0-9]{2}:){2}[0-9]{2}[¹²³]*','', txt)
    txt = re.sub('\[.*?\]','', txt)
    txt = re.sub(' +',' ', txt)
    txt = txt.strip()
    txt = html.unescape(txt)
    txt = re.sub('\\_o<','',txt)
    txt = re.sub('>o_/','',txt)
    txt = re.sub('<','',txt)               

    return(txt)

def main():
    global last_id
    global previous_id

    liste_dictons = []

    for dicton in dictons.dictons:
        liste_dictons.extend(explode_message(clean_message(dicton)))

    random.shuffle(liste_dictons)

    sqlconn = create_connection("slybot_linuxfr/tribune.db")

    # create tables
    if sqlconn is not None:
        # create trbune table
        sql_create(sqlconn, sql_create_tribune_table)
 
        # create indexes
        sql_create(sqlconn, sql_create_tribune_timer_index)
        sql_create(sqlconn, sql_create_tribune_login_index)
    else:
        print("Error! cannot create the database connection.")
        return(1)
   
    while(True):

        r = get_board('https://linuxfr.org/board/index.xml')
        if (r.status == 200):
            parse_and_store_tribune(sqlconn, r.data)

        if previous_id != last_id and previous_id != 0:
            
            values = ( previous_id, last_id)
            cur = sqlconn.cursor()
            cur.execute(sql_select_posts, values)

            rows = cur.fetchall()

            # parse messages
            for row in rows:
                (post_id, post_timer, post_info, post_login, post_message) = row

                if re.findall(r'[a-z]+', post_message):

                    liste_messages = []
                    
                    liste_messages.extend(explode_message(clean_message(post_message)))

                    # Prends n messages au hasard dans la base
                    # Dont le dernier
                    for i in range(0,20):
                        cur = sqlconn.cursor()
                        cur.execute(sql_select_random_posts, (post_id,))
                        (random_message,)= cur.fetchall()[0]

                        # Virer les norloges et les urls, les [], les espaces multiples, les <
                        liste_messages.extend(explode_message(clean_message(random_message)))

                    random.shuffle(liste_messages)

                    #Nombre de phrases à générer
                    nbphrases = random.randint(1,2)
                    #Nombre de propositions par phrase.
                    longphrasemax = random.randint(1,5)

                    # Test, 1/10 est une citation
                    citation = False
                    if(random.randint(1,10) == 5):
                        citation = True

                        liste_messages = liste_dictons
                        nbphrases = random.randint(1,2)
                        longphrasemax = random.randint(1,2)


                    reponse = ""

                    for phr in range(0, nbphrases):
                        indicepif = random.randint(0, len(liste_messages)-1)
                        phrase = liste_messages.pop(indicepif)
                        for prop in range(0, longphrasemax-1):
                            indicepif = random.randint(0, len(liste_messages)-1)
                            proposition = liste_messages.pop(indicepif)
                            phrase += ", "
                            phrase += proposition
                        phrase += ". "
                        reponse += phrase.capitalize()

                    # Prefix ?
                    if(random.randint(1,5) == 2):
                        reponse = random.choice(Prefix)+ " ? " + reponse

                    print(reponse)


        time.sleep(15)
main()
