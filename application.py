
import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session,json
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")
sym = SQL("sqlite:///list_of_symbols.db")
# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    rows = db.execute("SELECT symbol,SUM(shares) as totalshares FROM transactions where user_id=:id GROUP BY symbol HAVING totalshares>0",id=session["user_id"])
    table = []
    grand_total = 0
    for row in rows:
        share = lookup(row["symbol"])
        table.append({
            'symbol': share["symbol"],
            'name': share["name"],
            'shares': row["totalshares"],
            'price': usd(share["price"]),
            'total':usd(share["price"]*row["totalshares"])
        })
        grand_total += share["price"]*row["totalshares"]
    cash = db.execute("SELECT cash FROM users WHERE id =:id",id=session["user_id"])
    cash_in_hand = cash[0]["cash"]
    grand_total += cash_in_hand
    return render_template("index.html",stocks=table,cash=usd(cash_in_hand),grandtotal = usd(grand_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        quantity = int(request.form.get("Quantity"))
        sym = request.form.get("stock_symbol").upper()
        quote2 = lookup(sym)
        if not sym:
            return apology("No Symbol Entered",400)
        elif quote2 is None:
            return apology("Invalid Symbol",400)
        elif quantity <= 0:
            return apology("Quantity Must Be Positive",400)
        else:
            price_per_share = quote2["price"]
            user = db.execute("SELECT cash FROM users WHERE id = :user_id",user_id=session["user_id"])

            cash_in_hand = user[0]["cash"]
            total_price = price_per_share * quantity
            if total_price > cash_in_hand:
                return apology("You Don't Have Enough Funds",403)
            else:
                db.execute("UPDATE users SET cash = cash-:totalprice WHERE id=:user_id",totalprice = total_price,user_id = session["user_id"])
                db.execute("INSERT INTO transactions(user_id,symbol,shares,price) VALUES(:user_id,:symbol,:shares,:price)",
                user_id = session["user_id"],
                symbol = sym,
                shares = quantity,
                price = price_per_share
                )
                flash("BOUGHT")
                return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    rows = db.execute("SELECT symbol,shares,price,transaction_time FROM transactions where user_id = :id",id=session["user_id"])
    table = []
    for row in rows:
        table.append({
            'symbol': row["symbol"],
            'shares': row["shares"],
            'price': usd(row["price"]),
            'time': row["transaction_time"]
        })
    return render_template("history.html",rows = table)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        quote1 = lookup(symbol)
        if quote1 is None:
            return apology("invalid symbol",399)
        else:
            return render_template("afterquote.html",stock = {
                'name' : quote1["name"],
                'symbol' : quote1['symbol'],
                'price' : usd(quote1['price'])
            })
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Must provide username",403)
        if not request.form.get("password"):
            return apology("Must provide password",403)
        if not request.form.get("Confirm_Password"):
            return apology("Must confirm password",403)
        if not request.form.get("password") == request.form.get("Confirm_Password"):
            return apology("Passwords don't match",403)

        rows = db.execute("SELECT * FROM users WHERE username=:username",username=request.form.get("username"))
        if len(rows) == 1:
            return apology("Username Taken",403)
        else:
            session["user_id"] = db.execute("INSERT INTO users('username','hash') VALUES(:username,:hash)",username=request.form.get("username"),hash=generate_password_hash(request.form.get("password")))
            flash("Registered!")
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        quantity = int(request.form.get("Quantity"))
        sym = request.form.get("Symbol").upper()
        quote2 = lookup(sym)
        if not sym:
            return apology("No Symbol Entered",400)
        elif quote2 is None:
            return apology("Invalid Symbol",400)
        elif quantity <= 0:
            return apology("Quantity Must Be Positive",400)
        else:
            price_per_share = quote2["price"]
            total_shares=db.execute("SELECT symbol,SUM(shares) as totalshares FROM transactions where user_id =:id GROUP BY symbol HAVING totalshares>0",id = session["user_id"])
            total_price = price_per_share * quantity
            for row in total_shares:
                if row["symbol"] == sym:
                    if quantity > row["totalshares"]:
                        return apology("You Do not own As Many Shares As you Like To Sell",403)
            db.execute("INSERT INTO transactions (user_id,symbol,shares,price) VALUES (:id,:symbol,:shares,:price)",id = session["user_id"],symbol=sym,shares=-1*quantity,price=price_per_share)
            db.execute("UPDATE users SET cash = cash+:totalprice WHERE id=:user_id",totalprice = total_price,user_id = session["user_id"])
            flash("SOLD")
            return redirect("/")
    else:
        rows = db.execute("SELECT symbol from transactions where user_id = :id GROUP BY symbol HAVING SUM(shares)>0",id = session["user_id"])
        return render_template("sell.html",symbols = [row["symbol"] for row in rows])


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    if request.method == "POST":
        cash_to_add = request.form.get("add_cash")
        db.execute("UPDATE users SET cash = cash+:amount WHERE id=:user_id",amount=cash_to_add,user_id = session["user_id"])
        return redirect("/")
    else:
        cash = db.execute("SELECT cash FROM users WHERE id =:id",id=session["user_id"])
        cash_in_hand = usd(cash[0]["cash"])
        return render_template("add_cash.html",cash=cash_in_hand)

@app.route("/list_symbols")
@login_required
def symbols_list():
    symbols = sym.execute("SELECT Symbol,Name from symbols")
    length_symbols=len(symbols)
    return render_template("list_symbols.html",symbols=symbols,length=length_symbols)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
