from	datetime	import	datetime
from	app.extensions	import	db


class	Vehicle(db.Model):
    __tablename__	=	"vehicles"
    id	=	db.Column(db.Integer,	primary_key=True)
    reg_no	=	db.Column(db.String(20),	unique=True,	nullable=False)
    make	=	db.Column(db.String(50))
    year	=	db.Column(db.Integer)
    type	=	db.Column(db.String(30))
    ownership	=	db.Column(db.String(50))
    status	=	db.Column(db.String(20),	default="active")
    #	active	/	under_maintenance	/	out_of_service	/	retired
    created_at	=	db.Column(db.DateTime,	default=datetime.utcnow)  
    
    
    
class	VehicleDocument(db.Model):
    __tablename__	=	"vehicle_documents"
    id	=	db.Column(db.Integer,	primary_key=True)
    vehicle_id	=	db.Column(db.Integer,	db.ForeignKey("vehicles.id"),	nullable=False)
    doc_type	=	db.Column(db.String(30))			#	insurance	/	logbook	/	inspection
    document_number	=	db.Column(db.String(50))
    issue_date	=	db.Column(db.Date)
    expiry_date	=	db.Column(db.Date)
    
    
class	MaintenanceRecord(db.Model):
    __tablename__	=	"maintenance_records"
    id	=	db.Column(db.Integer,	primary_key=True)
    vehicle_id	=	db.Column(db.Integer,	db.ForeignKey("vehicles.id"),	nullable=False)
    created_by	=	db.Column(db.Integer,	db.ForeignKey("employees.id"))
    description	=	db.Column(db.Text)
    cost	=	db.Column(db.Numeric(10,	2))
    date	=	db.Column(db.Date,	default=datetime.utcnow)
    
    
class	Allocation(db.Model):
    __tablename__	=	"allocations"
    id	=	db.Column(db.Integer,	primary_key=True)
    driver_id	=	db.Column(db.Integer,	db.ForeignKey("employees.id"),	nullable=False)
    conductor_id	=	db.Column(db.Integer,	db.ForeignKey("employees.id"),	nullable=False)
    vehicle_id	=	db.Column(db.Integer,	db.ForeignKey("vehicles.id"),	nullable=False)
    route_id	=	db.Column(db.Integer,	db.ForeignKey("routes.id"),	nullable=False)
    status	=	db.Column(db.String(20),	default="active")		#	active	/	ended
    started_at	=	db.Column(db.DateTime,	default=datetime.utcnow)
    ended_at	=	db.Column(db.DateTime,	nullable=True)
    created_by	=	db.Column(db.Integer,	db.ForeignKey("employees.id"))
    
    
class	Accident(db.Model):
    __tablename__	=	"accidents"
    id	=	db.Column(db.Integer,	primary_key=True)
    vehicle_id	=	db.Column(db.Integer,	db.ForeignKey("vehicles.id"),	nullable=False)
    driver_id	=	db.Column(db.Integer,	db.ForeignKey("employees.id"))
    reported_by	=	db.Column(db.Integer,	db.ForeignKey("employees.id"))		#	Inspector
    description	=	db.Column(db.Text)
    date	=	db.Column(db.DateTime,	default=datetime.utcnow)
    status	=	db.Column(db.String(20),	default="open")