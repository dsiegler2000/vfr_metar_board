icao = document.querySelector("#icao").value

// Fetch compute will force an async computation of historical METAR data
fetch("/historical_metar_fetch_compute/" + icao).then()

// Chart data will return currently stored historical METARs
//  If historical METARs are not yet fetched & computed, this returns nothing
fetch("/historical_metar_chart_data/" + icao)
.then(response => response.text())
.then(data => console.log('Data received:', data))
.catch(error => {
    console.error('Error fetching historical weather stats:', error);
});

addEventListener("keypress", (event) => { 
    console.log(event['key']);
    if (event['key'] == 'a') {
        Highcharts.charts[0].series[0].points[0].onMouseOver();
    }
    else if (event['key'] == 'b') {
        Highcharts.charts[0].series[1].points[0].onMouseOver();
    }
    else if (event['key'] == 'c') {
        Highcharts.charts[0].series[1].points[1].onMouseOver();
    }
    else if (event['key'] == 'd') {
        Highcharts.charts[0].tooltip.hide()
    }
})

document.addEventListener('DOMContentLoaded', function () {
const chart = Highcharts.chart('container', {
    chart: {
        type: 'bar'
    },
    title: {
        text: 'Fruit Consumption'
    },
    xAxis: {
        categories: ['Apples', 'Bananas', 'Oranges']
    },
    yAxis: {
        title: {
            text: 'Fruit eaten'
        }
    },
    series: [{
        name: 'Jane',
        data: [1, 0, 4]
    }, {
        name: 'John',
        data: [5, 7, 3]
    }]
});
});