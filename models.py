from app import db
from sqlalchemy.dialects.postgresql import JSON





class Result(db.Model):
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String)
    result = db.Column(JSON)
    userid = db.Column(db.Integer)

    def __init__(self, ticker, result, userid):
        self.ticker = ticker
        self.result = result
        self.userid = userid

    def __repr__(self):
        return '<id {}>'.format(self.id)





class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String)

    def __init__(self, phone):
        self.phone = phone

    def __repr__(self):
        return '<id {}>'.format(self.id)

class Recent(db.Model):
    __tablename__ = 'recent'

    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.Integer)

class Follow(db.Model):
    __tablename__ = 'follows'

    id = db.Column(db.Integer, primary_key=True)
    userid = db.Column(db.Integer)
    tickerid = db.Column(db.Integer)

class Ticker(db.Model):
    __tablename__ = 'tickers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String())
    asking_price = db.Column(db.Float)

