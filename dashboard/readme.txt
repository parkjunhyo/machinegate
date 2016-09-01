pip install Flask
pip install simplejson
pip install httpie


root@ubuntu:~/machinegate/dashboard# cat templates/f5/stats_chart.html 
<!doctype html>
<title>Hello from Flask</title>
{% if name %}
  <h1>Hello {{ name }}!</h1>
{% else %}
  <h1>Hello World!</h1>
{% endif %}

{% set listvalue = [ 1,2,3 ] %}
{% for item in listvalue %}
   {{ item }}
{% endfor %} 

{% set listvalue = {"name":"seoul"} %}
{% for key, value in listvalue.iteritems() %}
   {{ listvalue[key] }}
{% endfor %}

{% for key, value in sample_dict.iteritems() %}
     <dt>{{ key }}</dt>
     <dt>{{ sample_dict[key] }}</dt>
     <dt>{{ value|length }}</dt>
     {% for item in value %}
            <dd>{{ item }}</dd>
     {% endfor %}
{% endfor %}


<html>
  <head>
    <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
    <script type="text/javascript">
      google.charts.load('current', {'packages':['corechart']});
      google.charts.setOnLoadCallback(drawChart);

      var sample = [[1,2,3],[4,5,6]]
      for (i=1;i<3;i++){
        console.log(i)
      }
      for (i=0;i<sample.length;i++){
         for (j=0;j<sample[i].length;j++){
            console.log(sample[i][j])
         }
      }
      var sample = {"one":10,"two":20}
      for (var key in sample){
         console.log(sample[key])
      }

      var sample = []
      for (i=1;i<5;i++){
         sample.push(i)
      }
      console.log(sample)

      var sample = {}
      for (i=1;i<5;i++){
         sample[i] = i*10
      }
      console.log(sample)

      function drawChart() {
        var data = google.visualization.arrayToDataTable([
          ['Year', 'Sales', 'Expenses'],
          ['2004',  1000,      400],
          ['2005',  1170,      460],
          ['2006',  660,       1120],
          ['2007',  1030,      540]
        ]);

        var options = {
          title: 'Company Performance',
          curveType: 'function',
          legend: { position: 'bottom' },
          fontSize: 10,
        };


        var chart = new google.visualization.LineChart(document.getElementById('curve_chart'));

        chart.draw(data, options);
      }
    </script>
  </head>
  <body>
    <div id="curve_chart" style="width: 900px; height: 500px"></div>
  </body>
</html>

