from flask import Flask, render_template, request, jsonify, url_for, redirect
import json
from os import environ
environ["REPLIT_DB_URL"] = "https://kv.replit.com/v0/eyJhbGciOiJIUzUxMiIsImlzcyI6ImNvbm1hbiIsImtpZCI6InByb2Q6MSIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjb25tYW4iLCJleHAiOjE2NzgyNjU3MjYsImlhdCI6MTY3ODE1NDEyNiwiZGF0YWJhc2VfaWQiOiJkNzg5ZTk4MS03MTllLTQ2ZWEtYWM4ZC03NWExMmY3MWM1ZTIiLCJ1c2VyIjoibWlsbGVyZHlsYW44NyIsInNsdWciOiJwZXJzb25hbC1maW5hbmNlLWRhc2hib2FyZCJ9.fyZpznRKGK2TQ1wfsuFZFcTY3r_CCxsQgeP8vRebRDZ50t0-pPqUC-S0r9SX5J_e2X6ep_YzZQ3987uevpNiJw"
from replit import db
from bs4 import BeautifulSoup
import requests
import time
from flask_debugtoolbar import DebugToolbarExtension


"""
Support for fractional shares.
The ability to record the sale of shares.
Timestamps for purchase (and sale) records.
"""

site = Flask(__name__)

# FLASK DEBUGGING
# site.debug = True
# site.config['SECRET_KEY'] = '386-392-779'
# site.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
# toolbar = DebugToolbarExtension(site)

def get_price(ticker):
    """Try/Except. If ticker is invalid, return None. Only nonexistent tickers will get to this point, and return none.
    This was the function of the forked code (checking for none) but it wasn't checking correctly and would error."""
    try:
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
    except:
        return None
    

@site.route('/')
def index():
    return render_template('index.html')


@site.route('/buy', methods=['POST'])
def buy():
    # Create shares key if it doesn't exist
    if 'shares' not in db.keys():
        db['shares'] = {}

    ticker = request.form['ticker']
    # validate for null tickers and numbers
    try:
        assert len(ticker) > 0
        assert ticker.isalpha()
    except AssertionError:
        # we could put an error state to alert specifically which error caused a void result, but this isn't a requirement...
        # The error is still handled as void and the db isn't affected.
        return redirect(url_for("index"))

    # remove starting $
    if ticker[0] == '$':
        ticker = ticker[1:]

    # uppercase and maximum five characters
    ticker = ticker.upper()[:5]

    current_price = get_price(ticker)

    if not get_price(ticker): # reject invalid tickers
        # return f"Ticker '{ticker}' not found."
        # The above line is the original error handling, which is ineffective because you have to go back,
        # instead of being able to continue with another attempt in addition to the ticker not actually returning 'None".
        return redirect(url_for("index"))

    price = float(current_price)

    try:
        if not request.form['shares']: # buy one if number not specified
            shares = float(1.0)
        else:
            # handling to assert a positive number only.
            shares = float(request.form['shares'])
            assert shares > 0
    except:
        #again, an error results in a void action and the user may continue.
        return redirect(url_for("index"))

    if ticker not in db['shares']: # buying these for the first time
        db['shares'][ticker] = { 'total_shares': shares,
                                 'total_cost': shares * price,
                                 'total_cost_per_share': price}

        db['shares'][ticker]['purchases'] = [{
                                'shares': shares,
                                'price': price,
                                'time_and_date_bought': time.time()
                                }]
    else: # buying more
        db['shares'][ticker]['total_shares'] += shares
        db['shares'][ticker]['total_cost'] += shares * price
        db['shares'][ticker]['total_cost_per_share'] += price
        db['shares'][ticker]['purchases'].append({
                                        'shares': shares,
                                        'price': price,
                                        'time_and_date_bought': time.time()
                                        })

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
    try:
        assert len(ticker) > 0
        assert ticker.isalpha()
    except AssertionError:
        # return "Invalid ticker, please reload the page."
        return redirect(url_for("index"))
    try:
        shares = float(request.form['shares'])
        assert shares > 0
    except:
        return redirect(url_for("index"))

    if ticker not in db['shares'] or shares > db['shares'][ticker]['total_shares']:
        return f"Invalid ticker or insufficient shares: {ticker} {shares}"

    # Get current price
    current_price = float(get_price(ticker))
    if not current_price: # reject invalid tickers
        return f"Ticker $'{ticker}' not found"

    total_cost_per_share = db['shares'][ticker]['total_cost'] / db['shares'][ticker]['total_shares']
    total_cost = db['shares'][ticker]['total_cost']

    # Update the soldPortfolio
    if ticker not in db['soldPortfolio']:
        db['soldPortfolio'][ticker] = { 'sold_shares': shares,
                                        'sold_price': current_price,
                                        'sold_at': time.time(),
                                        'purchase_cost_per_share': total_cost_per_share,
                                        'purchase_cost_total': total_cost,
                                        }
    else:
        db['soldPortfolio'][ticker]['sold_shares'] += shares
        db['soldPortfolio'][ticker]['sold_price'] = current_price

    # Update shares
    db['shares'][ticker]['total_shares'] -= shares
    db['shares'][ticker]['total_cost'] -= (total_cost_per_share * shares)
    db['shares'][ticker]['purchases'].append({ 'shares': -shares, 'price': current_price })

    db['shares'][ticker]['current_price'] = current_price
    db['shares'][ticker]['last_updated'] = time.time()

    return redirect(url_for("index"))


@site.route('/soldPortfolio')
def soldPortfolio():
    # Create sold portfolio if it doesn't exist
    if "soldPortfolio" not in db.keys():
        return jsonify({})

    # Calculate total profit/loss for each sold ticker
    for ticker in db["soldPortfolio"].keys():
        sold_price = db["soldPortfolio"][ticker]["sold_price"]
        purchase_cost = db["soldPortfolio"][ticker]["purchase_cost_per_share"] * db['soldPortfolio'][ticker]['sold_shares']
        profit_loss = sold_price - purchase_cost
        db["soldPortfolio"][ticker]["profit_loss"] = profit_loss

    # Return updated sold portfolio as JSON
    sold_portfolio = json.loads(db.get_raw("soldPortfolio"))
    return jsonify(**sold_portfolio)


@site.route('/flush')
def flush_db():
    #The original code did not account for attempting to flush empty db.
    try:
        del db["shares"]
    except:
        pass
    try:
        del db["soldPortfolio"]
    except:
        pass
    return redirect(url_for("index"))


site.run(host='0.0.0.0', port=8080)