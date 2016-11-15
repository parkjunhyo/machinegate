#! /usr/bin/env python

from setting import RUN_HOST, RUN_PORT

from flask import Flask
app = Flask(__name__)

from f5.stats_virtual_list import stats_virtual_list as f5_stats_virtual_list
@app.route('/dashboard/f5/stats/virtual/')
@app.route('/dashboard/f5/stats/virtual/list/')
def dashboard_f5_stats_list():
      return f5_stats_virtual_list()

from f5.stats_chart import stats_chart as f5_stats_chart 
@app.route('/dashboard/f5/stats/virtual/<target>/')
@app.route('/dashboard/f5/stats/virtual/<target>/<before_time>/')
def dashboard_f5_stats_chart(target=None,before_time=int(0)):
      return f5_stats_chart(target,before_time)

from f5.stats_top_chart import stats_top_chart as f5_stats_top_chart
@app.route('/dashboard/f5/stats/virtual/top/<category>/<device_name>/')
@app.route('/dashboard/f5/stats/virtual/top/<category>/<device_name>/<before_time>/')
def dashboard_f5_stats_top_chart(category=None,device_name=None,before_time=0):
      return f5_stats_top_chart(category,device_name,before_time)

from f5.virtual_profile_clientside import virtual_profile_clientside as f5_virtual_profile_clientside
@app.route('/dashboard/f5/virtual/profile/clientside/')
def dashboard_f5_virtual_profile_clientside():
      return f5_virtual_profile_clientside()

from f5.showl4list import showl4list as f5_showl4list
@app.route('/dashboard/f5/showl4list/')
def dashboard_f5_showl4list():
      return f5_showl4list()



#@app.route('/hello/')
#@app.route('/hello/<name>')
#def hello(name=None):
#    return route_hello(name)
#    #return render_template('hello.html', name=name)

if __name__ == '__main__':
    from os import environ
    app.run(host=RUN_HOST,port=environ.get("PORT", RUN_PORT),threaded=True)
