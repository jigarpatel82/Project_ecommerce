import datetime
import os
import gunicorn
from decouple import config
from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for, jsonify)
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor, CKEditorField
from flask_dropzone import Dropzone
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_toastr import Toastr
from flask_uploads import IMAGES, UploadSet, configure_uploads
from flask_wtf import FlaskForm, RecaptchaField
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from wtforms import (BooleanField, DateField, PasswordField, SelectField,
                     StringField, SubmitField, FileField)
from wtforms.validators import DataRequired
import base64
import stripe, json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
db = SQLAlchemy(app)
bootstrap = Bootstrap(app)
ckeditor = CKEditor(app)
dropzone = Dropzone(app)

# app.config['RECAPTCHA_USE_SSL'] = False
# app.config['RECAPTCHA_PUBLIC_KEY'] = 'public'
# app.config['RECAPTCHA_PRIVATE_KEY'] = 'private'
# app.config['RECAPTCHA_OPTIONS'] = {'theme': 'white'}

# Dropzone settings # DID NOT USE IN THE PROJECT BUT WILL USE IN FUTURE.
# dropzone_default_message = '<h5>Drop files here<br></h5>Or<br><button type="button" class="btn btn-primary">Click to Upload</button>'
# app.config['DROPZONE_UPLOAD_MULTIPLE'] = True
# app.config['DROPZONE_ALLOWED_FILE_CUSTOM'] = True
# app.config['DROPZONE_ALLOWED_FILE_TYPE'] = 'image/*'
# app.config['DROPZONE_REDIRECT_VIEW'] = None
# app.config['DROPZONE_IN_FORM'] = True
# app.config['DROPZONE_DEFAULT_MESSAGE'] = dropzone_default_message
# app.config['DROPZONE_UPLOAD_ON_CLICK'] = True
# app.config['DROPZONE_UPLOAD_ACTION'] = 'add_product'
# app.config['DROPZONE_UPLOAD_BTN_ID'] = 'submit'

# Uploads settings IF want to save files to upload folder
# app.config['UPLOADED_PHOTOS_DEST'] = os.getcwd() + '/uploads'
# photos = UploadSet('photos', IMAGES)
# configure_uploads(app, photos)

# stripe set up
stripe.api_key = os.environ.get('STRIPE_API_KEY')
# customers = stripe.Customer.list()
# print(customers)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    

class ProductData(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    image_filename = db.Column(db.String(40), nullable=False)
    image_data = db.Column(db.LargeBinary, nullable=False)
    decoded_image_data = db.Column(db.String(2000), nullable=False)
    image_mimetype = db.Column(db.String(50), nullable=False)
    product_price = db.Column(db.Float(precision=2), nullable=False)
    product_cost = db.Column(db.Float(precision=2), nullable=False)
    

with app.app_context():
    db.create_all()


class AddProduct(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    description = CKEditorField("Description", validators=[DataRequired()])
    image = FileField('Image File')
    product_price = StringField("Product price", validators=[DataRequired()], render_kw={"placeholder": "US$ 0.00"})
    product_cost = StringField("Product cost", validators=[DataRequired()], render_kw={"placeholder": "US$ 0.00"})
    submit = SubmitField('Save')

class AddUser(FlaskForm):
    name = StringField('Name', validators=[DataRequired()], render_kw={"placeholder": "Enter your name"})
    email = StringField('Email Address', validators=[DataRequired()], render_kw={"placeholder": "Enter your email"})
    password = PasswordField('Password', validators=[DataRequired()], render_kw={"placeholder": "Enter your password"})
    reenter_password = PasswordField('Reenter Password', validators=[DataRequired()], render_kw={"placeholder": "Reenter your password"})
    submit = SubmitField('Register')

class CheckoutUser(FlaskForm):
    email = StringField('Email Address', validators=[DataRequired()])
    first_name = StringField('First name', validators=[DataRequired()])
    last_name = StringField('Last name', validators=[DataRequired()])
    address1 = StringField('Address Line 1', validators=[DataRequired()])
    address2 = StringField('Address Line 2')
    city = StringField('City', validators=[DataRequired()])
    province = StringField('Province', validators=[DataRequired()])
    country = StringField('Country', validators=[DataRequired()])
    postal_code = StringField('Postal code', validators=[DataRequired()])
    phone = StringField('Phone', validators=[DataRequired()])
    # recaptcha = RecaptchaField()
    submit = SubmitField('Continue to Payment')

# LOGIN MANAGEMENT
login_manager = LoginManager()
login_manager.init_app(app)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

## ADMIN ONLY DECORATOR
def admin_only(function):
    @wraps(function)
    def decorator_func(*args, **kwargs):
        if current_user.get_id() != '1':
            return abort(403)
        else:
            return function(*args, **kwargs)
    return decorator_func

# OTHER FUNCTIONS
def cart_data(browser_session , db):
    cart_items = {}
    for item in browser_session:
        product = db.query.filter_by(id=item).first()
        if product not in cart_items:
            cart_items[product] = int(1)
        else:
            cart_items[product] += 1
    return cart_items

def get_year():
    today = datetime.datetime.today()
    year = today.strftime('%Y')
    return year


# main route
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'product' not in session:       
        session['product'] = []
    items = len(session['product'])
    year = get_year()
    return render_template('index.html', year=year, items=items)


# logout user
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/products')
def products(): 
    if ProductData:
        products = ProductData.query.all()
    items = len(session['product'])
    year = get_year()   
    return render_template('products.html', products=products, year=year, items=items)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/dashboard/product_manager')
def product_manager():
    if ProductData:
        product_data = ProductData.query.all()
    return render_template('product_manager.html', product_data=product_data)

@app.route('/image')
def render_image():
    image_data = ProductData.query.filter_by(ProductData.Image_data).all()


@app.route('/dashboard/product_manager/add_product', methods=['GET', 'POST'])
def add_product():
    form = AddProduct()
    if form.validate_on_submit():
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            image = request.files.get('file')
            data = base64.b64encode(image.read())
            decoded_image_data = base64.b64decode(data)
            image_mimetype = image.mimetype
            product_price = request.form.get('product_price')
            product_cost = request.form.get('product_cost')
            product_data = ProductData(title=title, description=description, image_data=data, decoded_image_data=decoded_image_data, image_mimetype=image_mimetype ,image_filename= image.filename, product_price=product_price, product_cost=product_cost)
            db.session.add(product_data)
            db.session.commit()
            return redirect(url_for('product_manager'))
    return render_template('add_product.html', form=form)

@app.route('/dashboard/product_manager/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = ProductData.query.get(product_id)
    edit_product_form = AddProduct(
        title = product.title,
        description = product.description,
        image = product.image_data,
        product_price = product.product_price,
        product_cost = product.product_cost,
    )
    print('this part is done')
    if request.method == 'POST':
        product.title = edit_product_form.title.data
        product.description = edit_product_form.description.data
        product.image = edit_product_form.image.data
        product.product_price = edit_product_form.product_price.data
        product.product_cost = edit_product_form.product_cost.data
        print('updated')
        db.session.commit()
        return redirect(url_for('product_manager'))       
    return render_template('add_product.html',form=edit_product_form)


@app.route('/delete/<int:product_id>')
def delete_product(product_id):
    product = ProductData.query.get(product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('product_manager'))

@app.route('/add/<int:product_id>', methods=['GET', 'POST'])
def add_to_cart(product_id):
    session.permanent = True
    session['product'].append(product_id)
    items = len(session['product'])
    print(session, items)
    year=get_year()   
    return render_template('products.html', items=items, year=year)

@app.route('/cart', methods=['GET', 'POST'])
def load_cart():
    items = len(session['product'])
    print(session['product'])
    # cart_items = {}
    # for item in session['product']:
    #     product = ProductData.query.filter_by(id=item).first()
    #     if product not in cart_items:
    #         cart_items[product] = int(1)
    #     else:
    #         cart_items[product] += 1
    # print(cart_items)
    cart_items = cart_data(browser_session=session['product'], db=ProductData)
    print(cart_items)
    global total 
    total = 0
    for key, value in cart_items.items():
        subtotal = key.product_price * value
        total += subtotal
    year = get_year()
    return render_template('shopping_cart.html',cart_items=cart_items, items=items, total=total, year=year)


@app.route('/signup', methods= ['GET', 'POST'])
def signup():
    form = AddUser()
    error = None
    if form.validate_on_submit():
        if request.method == 'POST':
            email = request.form['email'].lower()
            user = User.query.filter_by(email=email).first()
            if user:
                flash('You already have an account. Please login instead')
                return redirect(url_for('login'))
            else:                
                name = request.form['name'].title()
                # IF YOU DON'T WANT TO USE REQUEST THEN USE(ONLY WORKS IN WTF FORMS):
                # name = form.name.data
                password = request.form['password']
                reenter_password = request.form['reenter_password']
                print(name,password, reenter_password)
                if password == reenter_password:
                    password = generate_password_hash(password=request.form['password'], method='pbkdf2:sha256', salt_length=8)
                    new_user = User(name=name, email=email, password=password)
                    db.session.add(new_user)
                    db.session.commit()
                    login_user(user=new_user)
                    return redirect(url_for('index'))
                else:
                    error = 'Both password fields does not match' 
                    print(error) 
                    flash(message=error, category='alert-danger')             
    return render_template('signup.html', form=form, error=error)

@app.route('/create-checkout-session', methods=['GET', 'POST'])
def create_checkout_session():
    cart_items = cart_data(browser_session=session['product'], db=ProductData)
    stripe_line_items = []
    for key, value in cart_items.items():
        cart_product = {'price_data':{
                        'currency': 'cad',
                        'product_data': {
                            'name': key.title,
                            },
                        'unit_amount': int(key.product_price * 100)
                    }, 'quantity': value}
        stripe_line_items.append(cart_product)   
    stripe_session = stripe.checkout.Session.create(
        line_items=stripe_line_items,
        shipping_address_collection={"allowed_countries": ["US", "CA"]},
          shipping_options=[
            {
            "shipping_rate_data": {
                "type": "fixed_amount",
                "fixed_amount": {"amount": 500, "currency": "cad"},
                "display_name": "Free shipping",
                "delivery_estimate": {
                "minimum": {"unit": "business_day", "value": 5},
                "maximum": {"unit": "business_day", "value": 7},
                },
            },
            },
        ],
        mode='payment',
        success_url='http://localhost:4242/success',
        cancel_url='http://localhost:4242/cancel',
    )
    return redirect(stripe_session.url, code=303)   

@app.route('/success', methods= ['GET', 'POST'])
def success():
    return render_template('success.html')

@app.route('/update_cart_add/<int:product_id>', methods=['GET', 'POST'])
def update_cart_add(product_id):
    session.permanent = True
    session['product'].append(product_id)
    items = len(session['product'])
    return redirect(url_for('load_cart'))

@app.route('/update_cart_remove/<int:product_id>', methods=['GET', 'POST'])
def update_cart_remove(product_id):
    session.permanent = True
    session['product'].remove(product_id)
    items = len(session['product'])
    return redirect(url_for('load_cart'))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True) 
 
    
if __name__ == '__main__':
    app.run(debug=True)