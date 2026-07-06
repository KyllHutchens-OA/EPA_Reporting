from database import db

class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    entries = db.relationship('DataEntry', backref='site', lazy=True)
    schematics = db.relationship('Schematic', backref='site', lazy=True)

class DataEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.String(200))

class Schematic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
