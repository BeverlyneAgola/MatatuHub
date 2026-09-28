from	datetime	import	datetime
from	app.extensions	import	db


class	TripLog(db.Model):
    __tablename__	=	"trip_logs"
    id	=	db.Column(db.Integer,	primary_key=True)
    allocation_id	=	db.Column(db.Integer,	db.ForeignKey("allocations.id"),	nullable=False)
    driver_id	=	db.Column(db.Integer,	db.ForeignKey("employees.id"),	nullable=False)
    start_time	=	db.Column(db.DateTime,	default=datetime.utcnow)
    end_time	=	db.Column(db.DateTime,	nullable=True)
    notes	=	db.Column(db.Text)
    
    
class	PaymentLog(db.Model):
    __tablename__	=	"payment_logs"
    id	=	db.Column(db.Integer,	primary_key=True)
    conductor_id	=	db.Column(db.Integer,	db.ForeignKey("employees.id"),	nullable=False)
    allocation_id	=	db.Column(db.Integer,	db.ForeignKey("allocations.id"),	nullable=False)
    route_id	=	db.Column(db.Integer,	db.ForeignKey("routes.id"),	nullable=False)
    vehicle_id	=	db.Column(db.Integer,	db.ForeignKey("vehicles.id"),	nullable=False)
    direction	=	db.Column(db.String(50),	nullable=False)
    time_band	=	db.Column(db.String(20),	nullable=False)					
    #	auto-detected,	not	chosen
    fare_amount	=	db.Column(db.Numeric(10,	2),	nullable=False)
    amount_given	=	db.Column(db.Numeric(10,	2),	nullable=False)
    change_given	=	db.Column(db.Numeric(10,	2),	nullable=False)
    commuter_phone	=	db.Column(db.String(20),	nullable=False)
    payment_status	=	db.Column(db.String(20),	default="pending")		#	pending/confirmed/failed
    transaction_ref	=	db.Column(db.String(50),	nullable=True)
    created_at	=	db.Column(db.DateTime,	default=datetime.utcnow)