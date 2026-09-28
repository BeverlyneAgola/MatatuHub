from	app.extensions	import	db


class	Route(db.Model):
    __tablename__	=	"routes"
    id	=	db.Column(db.Integer,	primary_key=True)
    name	=	db.Column(db.String(100),	nullable=False)
    start_point	=	db.Column(db.String(100),	nullable=False)
    destination	=	db.Column(db.String(100),	nullable=False)
    status	=	db.Column(db.String(20),	default="active")		#	active	/	inactive
    
    
class	Fare(db.Model):
    __tablename__	=	"fares"
    id	=	db.Column(db.Integer,	primary_key=True)
    route_id	=	db.Column(db.Integer,	db.ForeignKey("routes.id"),	nullable=False)
    direction	=	db.Column(db.String(50),	nullable=False)						
    time_band	=	db.Column(db.String(20),	nullable=False)						
    amount	=	db.Column(db.Numeric(10,	2),	nullable=False)
    effective_from	=	db.Column(db.Date,	nullable=False)
    effective_until	=	db.Column(db.Date,	nullable=True)							
    #	e.g.	"Towards	CBD"
    #	peak	/	off_peak
    #	null	=	still	current
    
    
class	Schedule(db.Model):
    __tablename__	=	"schedules"
    id	=	db.Column(db.Integer,	primary_key=True)
    route_id	=	db.Column(db.Integer,	db.ForeignKey("routes.id"),	nullable=False)
    departure_time	=	db.Column(db.Time,	nullable=False)
    created_by	=	db.Column(db.Integer,	db.ForeignKey("employees.id"))