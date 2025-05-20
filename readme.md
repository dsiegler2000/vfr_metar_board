```
ssh pi
chromium-browser --app=http://127.0.0.1:5000/metar/o69 --start-fullscreen
python3 -m venv env --system-site-packages && source env/bin/activate && pip install -r requirements.txt
export FLASK_APP=app
export FLASK_ENV=development
flask --app app.py --debug run

dsiegler@192.168.0.233
# This should be updated to pipreq
pip freeze > requirements.txt

sudo apt-get install python-dev
sudo apt install python-dev-is-python3
sudo apt install python3-gpiozero
sudo apt install nodejs npm

cd static
npm install highcharts --save
```

Note: can get magnetic declination from https://aviationweather.gov/api/data/airport
https://forums.flightsimulator.com/t/propwash-dual-encoder-question/404874