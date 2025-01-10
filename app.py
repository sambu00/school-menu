import sqlite3
from datetime import date, timedelta
import calendar
from queue import SimpleQueue

from flask import Flask, redirect, url_for, request, render_template, g


app = Flask(__name__)


DATABASE = 'db/menu_rotation.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db
    
def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv
    
def chg_db_many(sql_stmt, args=()):
    cur = get_db().cursor()
    cur.execute('PRAGMA foreign_keys = ON')
    cur.executemany(sql_stmt, args)
    get_db().commit()
    
def chg_db_one(sql_stmt, args=()):
    cur = get_db().cursor()
    cur.execute('PRAGMA foreign_keys = ON')
    cur.execute(sql_stmt, args)
    get_db().commit()


@app.route('/')
def index():
    return redirect(url_for('meals'))


@app.route('/meals')
def meals():

    todays = []
    tomorrows = []
    
    # set dates
    current_date = date.today()
    next_date = current_date + timedelta(days=1)
    
    kids = fetch_kids()
    for kid in kids:
        todays.append(kid_meal_on_date(kid, current_date))
        tomorrows.append(kid_meal_on_date(kid, next_date))
            

    return render_template('meals.html', 
                           page_detail=' - Meals', 
                           meals_today=todays,
                           meals_tomorrow=tomorrows)


@app.route('/meal_date', methods=['GET', 'POST'])
def meal_date():
    form_date = '' 
    if request.method == 'POST':
        form_date = request.form['meal_date']

    current_date = date.today()
    meal_date = current_date if form_date == '' else date.fromisoformat(form_date)
    actual_day = calendar.day_name[0]
    
    todays = []
    
    kids = fetch_kids()
    for kid in kids:
        todays.append(kid_meal_on_date(kid, meal_date))
    
    return render_template('meal_on_date.html', 
                            page_detail=' - Meal on Date',
                            meal_date=meal_date,
                            day_of_week=calendar.day_name[calendar.weekday(meal_date.year, meal_date.month, meal_date.day)],
                            meals=todays)


@app.route('/kids', methods=['GET', 'POST'])
def kids():
    if request.method == 'POST':
        
        if request.form['action'] == 'add_kid':
            add_kid(request.form['kid_name'])
        elif request.form['action'] == 'remove_kid':
            remove_kid(request.form['kid_id'])
        
        return redirect(url_for('kids'))
        
    kids = fetch_kids() 
    return render_template('kids.html', 
                           page_detail=' - Kids',
                           kids=kids)


@app.route('/weeks', methods=['GET', 'POST'])
def weeks():
    form_col = ''
    if request.method == 'POST':
        form_col = request.form['kid_id']
        
        if request.form['action'] == 'add_week':
            add_week_meals()
        elif request.form['action'] == 'chg_meal':
            change_meal()
        elif request.form['action'] == 'remove_week':
            remove_meals()
        elif request.form['action'] == 'set_starting_meal':
            set_starer()

        else:
            pass
        
        
    
    kids = fetch_kids()
    meals = fetch_meals()
    
    
    selected = min_kid_id() if form_col == '' else int(form_col)
    
    return render_template('weeks.html',
                           page_detail=' - Weeks',
                           kids=kids,
                           meals=meals,
                           selected=selected)


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

### KIDS ACTIONS ###
def min_kid_id():
    rs = query_db('SELECT MIN(KID_ID) as MN FROM KIDS')
    return 0 if rs[0]['MN'] == None else rs[0]['MN']

def fetch_kids():
    return query_db('SELECT * FROM KIDS')

def add_kid(add_name):
    rs = query_db('SELECT MAX(KID_ID) as MX FROM KIDS')
    mx = rs[0]['MX']
    
    next_cnt = 0
    if mx != None:
       next_cnt = mx + 1
     
    chg_db_one('INSERT INTO KIDS VALUES (?,?)', (next_cnt, add_name))

def remove_kid(del_id):
    chg_db_one('DELETE FROM KIDS WHERE KID_ID = (?)', (del_id,))
    


### MEALS ACTIONS ###
def fetch_meals():
    return query_db('SELECT * FROM MEALS ORDER BY KID_ID, MEAL_ID')
    

def fetch_kid_meals(kid_id):
    return query_db('SELECT * FROM MEALS WHERE KID_ID = ? ORDER BY MEAL_ID', (kid_id,))


def insert_meals(kid_id, meals):
    rs = query_db('SELECT MAX(MEAL_ID) as MX FROM MEALS WHERE KID_ID = (?)', (kid_id,))
    mx = rs[0]['MX']
    next_cnt = 0 
    if mx != None:
        next_cnt = mx + 1
    
    chg_db_one('INSERT INTO MEALS VALUES (?, ?, ?)', (meals))



def add_week_meals():
    kid_id = int(request.form['kid_id'])
    
    search_max_meal = query_db('SELECT MAX(MEAL_ID) as MX FROM MEALS WHERE KID_ID = (?)', (kid_id,))
    next_meal = 0 if search_max_meal[0]['MX'] == None else search_max_meal[0]['MX'] + 1
    
    meals = []
    for i in range(7):
        meals.append( (kid_id, next_meal, request.form['meal' + str(i)]) )
        next_meal += 1
    
    
    chg_db_many('INSERT INTO MEALS VALUES (?, ?, ?)', meals)
    

def remove_meals():
    del_id = int(request.form['kid_id'])
    chg_db_one('DELETE FROM MEALS WHERE KID_ID = (?)', (del_id,))


def change_meal():
    kid_id = int(request.form['kid_id'])
    meal_id = int(request.form['meal_id'])
    meal_courses = request.form['meal_courses']
    
    chg_db_one('UPDATE MEALS SET MEAL_COURSES = ? WHERE KID_ID = ? AND MEAL_ID = ?', (meal_courses, kid_id, meal_id))


### STARTERS ACTIONS ###
def set_starer():
    kid_id = int(request.form['kid_id'])
    meal_id = int(request.form['meal_id'])
    meal_date = request.form['meal_date']
    
    rs = query_db('SELECT COUNT(*) as CNT FROM STARTERS WHERE KID_ID = ?', (kid_id, ))
    tot_rec = rs[0]['CNT']
    
    if tot_rec > 0:
        chg_db_one('UPDATE STARTERS SET MEAL_ID = ?, STARTING_DATE = ? WHERE KID_ID = ?', (meal_id, meal_date, kid_id))
    else:
        chg_db_one('INSERT INTO STARTERS VALUES (?, ?, ?)', (kid_id, meal_id, meal_date))
    

def get_starter(kid_id):
    rs = query_db('SELECT MEAL_ID, STARTING_DATE FROM STARTERS WHERE KID_ID = ?', (kid_id,))
    return None if rs == [] else rs[0]


### MEAL QUEUEING ###
def meal_at_date(starter_rec, target_date, meals_records):
    start_date = date.fromisoformat(starter_rec['STARTING_DATE'])
    date_diff = days_between(start_date, target_date)
    
    adj_list = meals_records[starter_rec['MEAL_ID']:] + meals_records[:starter_rec['MEAL_ID']]
    
    if date_diff < 0:
        adj_list.reverse()
        adj_list = adj_list[-1:] + adj_list[:-1]
        date_diff *= -1
    
    
    meals_queue = SimpleQueue()
    
    for el in adj_list:
        meals_queue.put(el['MEAL_COURSES'])
    
    # loop over queue
    for _ in range(date_diff):
         el = meals_queue.get()
         meals_queue.put(el)

    return meals_queue.get()
    


def days_between(date_start, date_end):
    td = date_start - date_end
    return td.days * -1

    
def kid_meal_on_date(kid, selected_date):
    rs = dict()
    
    starter_rec = get_starter(kid['KID_ID'])
    
    if starter_rec != None:
        meals_records = fetch_kid_meals(kid['KID_ID'])
        
        rs['name'] = kid['KID_NAME']
        rs['meal'] = meal_at_date(starter_rec, selected_date, meals_records)

    return rs


if __name__ == '__main__':
    app.run()