from flask import Flask, render_template, request, jsonify, url_for, redirect
import json
from os import environ
environ["REPLIT_DB_URL"] = "https://kv.replit.com/v0/eyJhbGciOiJIUzUxMiIsImlzcyI6ImNvbm1hbiIsImtpZCI6InByb2Q6MSIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjb25tYW4iLCJleHAiOjE2Nzc0NTY5NjMsImlhdCI6MTY3NzM0NTM2MywiZGF0YWJhc2VfaWQiOiJhYTNmMDAxNi0xMDYxLTQ1NWUtOTEzMC04MWEzMWE3ZTUwODEiLCJ1c2VyIjoibWlsbGVyZHlsYW44NyIsInNsdWciOiJFeHRlcm5hbFdvb3p5TWVhc3VyZW1lbnRzIn0.fS6k_qegyRTwuKpj2CtVWJpRINbBx-6lTnJqW9yTCJCHefLSfFBA6A5QtjFSSyxjsxfYYejcS_jC2iJlVQpNRA"
from replit import db
from bs4 import BeautifulSoup
import requests
import time

"""
Support for fractional shares. Done.
The ability to record the sale of shares.
Timestamps for purchase (and sale) records.
Support for cryptocurrencies, perhaps using data from CoinMarketCap.
The ability to create multiple portfolios or user accounts.
Graphs.
"""

site = Flask(__name__)

def get_price(ticker):

    # use cache if price is not stale
    if ticker in db["shares"].keys() and time.time() < db["shares"][ticker]["last_updated"]+60:
        return db["shares"][ticker]["current_price"]

    page = requests.get("https://finance.yahoo.com/quote/" + ticker)
    soup = BeautifulSoup(page.text, "html5lib")

    price = soup.find('fin-streamer', {'class':'Fw(b) Fz(36px) Mb(-4px) D(ib)'}).text

    # remove thousands separator
    price = price.replace(",", "")

    # update price in db
    if ticker in db["shares"].keys():
        db["shares"][ticker]["current_price"] = price
        db["shares"][ticker]["last_updated"] = time.time()

    return price
    

@site.route('/')
def index():
    return render_template('index.html')


@site.route('/buy', methods=['POST'])
def buy():
    # Create shares key if it doesn't exist
    if 'shares' not in db.keys():
        db['shares'] = {}

    ticker = request.form['ticker']

    # remove starting $
    if ticker[0] == '$':
        ticker = ticker[1:]

    # uppercase and maximum five characters
    ticker = ticker.upper()[:5]

    current_price = get_price(ticker)
    if not get_price(ticker): # reject invalid tickers
        return f"Ticker $'{ticker}' not found"

    if not request.form['price']: # use current price if price not specified
        price = float(current_price)
    else:
        price = float(request.form['price'])

    if not request.form['shares']: # buy one if number not specified
        shares = float(1.0)
    else:
        shares = float(request.form['shares'])

    if ticker not in db['shares']: # buying these for the first time
        db['shares'][ticker] = { 'total_shares': shares,
                                 'total_cost': shares * price }

        db['shares'][ticker]['purchases'] = [{ 'shares': shares,
                                'price': price }]
    else: # buying more
        db['shares'][ticker]['total_shares'] += shares
        db['shares'][ticker]['total_cost'] += shares * price
        db['shares'][ticker]['purchases'].append({ 'shares': shares,
                                        'price': price})

    db['shares'][ticker]['current_price'] = current_price
    db['shares'][ticker]['last_updated'] = time.time()

    return redirect(url_for("index"))

@site.route('/portfolio')
def portfolio():
    if "shares" not in db.keys():
        return jsonify({})

    portfolio = json.loads(db.get_raw("shares"))

    # Get current values
    for ticker in portfolio.keys():
        current_price = float(get_price(ticker))
        current_value = current_price * portfolio[ticker]['total_shares']
        portfolio[ticker]['current_value'] = current_value

    return jsonify(**portfolio)

@site.route('/sold', methods=['POST'])
def sold():
    # Create soldPortfolio key if it doesn't exist
    if 'soldPortfolio' not in db.keys():
        db['soldPortfolio'] = {}

    # Verify ticker and amount of shares
    ticker = request.form['ticker']
    shares = float(request.form['shares'])
    if ticker not in db['shares'] or shares > db['shares'][ticker]['total_shares']:
        return f"Invalid ticker or insufficient shares: {ticker} {shares}"

    # Get current price
    current_price = float(get_price(ticker))
    if not current_price: # reject invalid tickers
        return f"Ticker $'{ticker}' not found"

    # Profit calc
    total_cost = db['shares'][ticker]['total_cost']
    sold_cost = shares / db['shares'][ticker]['total_shares'] * total_cost
    profit = sold_cost - shares * current_price

    # Update the soldPortfolio
    if ticker not in db['soldPortfolio']:
        db['soldPortfolio'][ticker] = { 'total_shares': shares, 'total_cost': sold_cost }
    else:
        db['soldPortfolio'][ticker]['total_shares'] += shares
        db['soldPortfolio'][ticker]['total_cost'] += sold_cost

    # Update shares
    db['shares'][ticker]['total_shares'] -= shares
    db['shares'][ticker]['total_cost'] -= sold_cost
    db['shares'][ticker]['purchases'].append({ 'shares': -shares, 'price': current_price })

    db['shares'][ticker]['current_price'] = current_price
    db['shares'][ticker]['last_updated'] = time.time()

    # Return profit
    return f"Sold {shares} shares of {ticker} for ${current_price:.2f} each. Profit: ${profit:.2f}"



@site.route('/flush')
def flush_db():
    del db["shares"]
    return redirect(url_for("index"))


site.run(host='0.0.0.0', port=8080)