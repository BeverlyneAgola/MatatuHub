from	datetime	import	datetime
from	app.extensions	import	db


class	Payroll(db.Model):
    __tablename__	=	"payroll"
    id	=	db.Column(db.Integer,	primary_key=True)
    employee_id	=	db.Column(db.Integer,	db.ForeignKey("employees.id"),	nullable=False)
    period	=	db.Column(db.String(10),	nullable=False)			#	"2026-09"
    basic_salary	=	db.Column(db.Numeric(10,	2),	nullable=False)
    allowance	=	db.Column(db.Numeric(10,	2),	default=0)
    net_pay	=	db.Column(db.Numeric(10,	2))			#	computed	at	generation	time
    status	=	db.Column(db.String(20),	default="draft")		#	draft	/	issued
    generated_by	=	db.Column(db.Integer,	db.ForeignKey("employees.id"))
    generated_at	=	db.Column(db.DateTime,	default=datetime.utcnow)
    
    
class	PayrollDeduction(db.Model):
    __tablename__	=	"payroll_deductions"
    id	=	db.Column(db.Integer,	primary_key=True)
    payroll_id	=	db.Column(db.Integer,	db.ForeignKey("payroll.id"),	nullable=False)
    type	=	db.Column(db.String(30))			#	nhif	/	sacco	/	loan_repayment	/	other
    amount	=	db.Column(db.Numeric(10,	2),	nullable=False)
    

class	Claim(db.Model):
    __tablename__	=	"claims"
    id	=	db.Column(db.Integer,	primary_key=True)
    department	=	db.Column(db.String(30))								
    category	=	db.Column(db.String(30))											
    #	originating	dept,	e.g.	"Fleet"
    #	accident	/	insurance	/	servicing
    related_accident_id	=	db.Column(db.Integer,	db.ForeignKey("accidents.id"),	nullable=True)
    description	=	db.Column(db.Text)
    amount_requested	=	db.Column(db.Numeric(10,	2))
    status	=	db.Column(db.String(20),	default="pending")		#	pending	/	approved	/	rejected
    reviewed_by	=	db.Column(db.Integer,	db.ForeignKey("employees.id"),	nullable=True)
    created_at	=	db.Column(db.DateTime,	default=datetime.utcnow)
    reviewed_at	=	db.Column(db.DateTime,	nullable=True)
    
class	Compensation(db.Model):
    __tablename__	=	"compensations"
    id	=	db.Column(db.Integer,	primary_key=True)
    claim_id	=	db.Column(db.Integer,	db.ForeignKey("claims.id"),	nullable=False)
    amount	=	db.Column(db.Numeric(10,	2),	nullable=False)
    approved_by	=	db.Column(db.Integer,	db.ForeignKey("employees.id"))
    paid_at	=	db.Column(db.DateTime,	default=datetime.utcnow)
    
    
class	BudgetAllocation(db.Model):
    __tablename__	=	"budget_allocations"
    id	=	db.Column(db.Integer,	primary_key=True)
    department_id	=	db.Column(db.Integer,	db.ForeignKey("departments.id"),	nullable=False)
    amount	=	db.Column(db.Numeric(10,	2),	nullable=False)
    period	=	db.Column(db.String(10))
    allocated_by	=	db.Column(db.Integer,	db.ForeignKey("employees.id"))