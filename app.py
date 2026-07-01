from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

app.config['SECRET_KEY'] = 'change_this_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scoops.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

# ==========================
# DATABASE MODELS
# ==========================

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    customer_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=False)

    city = db.Column(db.String(100), nullable=False)
    street_name = db.Column(db.String(200), nullable=False)
    building = db.Column(db.String(200), nullable=False)
    floor_number = db.Column(db.String(50), nullable=False)

    total_price = db.Column(db.Float, nullable=False)

    status = db.Column(db.String(50), default='Pending')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey('order.id'),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey('product.id'),
        nullable=False
    )

    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')


# ==========================
# HOME
# ==========================

@app.route('/')
def home():
    products = Product.query.limit(4).all()
    return render_template('home.html', products=products)


# ==========================
# SHOP
# ==========================

@app.route('/shop')
def shop():
    search = request.args.get('search', '')

    if search:
        products = Product.query.filter(
            Product.name.contains(search)
        ).all()
    else:
        products = Product.query.all()

    return render_template(
        'shop.html',
        products=products,
        search=search
    )


# ==========================
# CONTACT
# ==========================

@app.route('/contact')
def contact():
    return render_template('contact.html')


# ==========================
# CART
# ==========================

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):

    product = Product.query.get_or_404(product_id)

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']

    product_id = str(product_id)

    if product_id in cart:
        cart[product_id] += 1
    else:
        cart[product_id] = 1

    session['cart'] = cart

    return redirect(url_for('shop'))


@app.route('/cart')
def cart():

    cart = session.get('cart', {})

    items = []
    total = 0

    for product_id, quantity in cart.items():

        product = Product.query.get(int(product_id))

        if product:
            subtotal = product.price * quantity

            items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })

            total += subtotal

    return render_template(
        'cart.html',
        items=items,
        total=total
    )
@app.route('/increase_quantity/<int:product_id>')
def increase_quantity(product_id):

    cart = session.get('cart', {})

    pid = str(product_id)

    if pid in cart:
        cart[pid] += 1

    session['cart'] = cart

    return redirect(url_for('cart'))


@app.route('/decrease_quantity/<int:product_id>')
def decrease_quantity(product_id):

    cart = session.get('cart', {})

    pid = str(product_id)

    if pid in cart:

        cart[pid] -= 1

        if cart[pid] <= 0:
            del cart[pid]

    session['cart'] = cart

    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):

    cart = session.get('cart', {})

    pid = str(product_id)

    if pid in cart:
        del cart[pid]

    session['cart'] = cart

    return redirect(url_for('cart'))


# ==========================
# CHECKOUT
# ==========================

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():

    cart = session.get('cart', {})

    if not cart:
        return redirect(url_for('shop'))

    items = []
    total = 0

    for product_id, quantity in cart.items():

        product = Product.query.get(int(product_id))

        if product:
            items.append({
                'product': product,
                'quantity': quantity
            })

            total += product.price * quantity

    delivery = 5
    final_total = total + delivery

    if request.method == 'POST':

        order = Order(
            customer_name=request.form['customer_name'],
            phone=request.form['phone'],
            city=request.form['city'],
            street_name=request.form['street_name'],
            building=request.form['building'],
            floor_number=request.form['floor_number'],
            total_price=final_total
        )

        db.session.add(order)
        db.session.commit()

        for item in items:

            product = Product.query.get(item['product'].id)

            if product.stock < item['quantity']:
                return "Not enough stock", 400

            product.stock -= item['quantity']

            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item['quantity'],
                price=product.price
            )

            db.session.add(order_item)

        db.session.commit()

        session.pop('cart', None)

        return redirect(url_for('dashboard'))

    return render_template(
        'checkout.html',
        total=total,
        delivery=delivery,
        final_total=final_total
    )

# ==========================
# DASHBOARD
# ==========================

@app.route('/dashboard')
def dashboard():

    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    products = Product.query.all()

    orders = Order.query.order_by(Order.created_at.desc()).all()

    return render_template(
        'dashboard.html',
        products=products,
        orders=orders
    )

@app.route("/admin")
def admin():
    return render_template("admin.html")


# ==========================
# ADD PRODUCT
# ==========================

@app.route('/product/add', methods=['GET', 'POST'])
def add_product():

    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':

        file = request.files.get('image')

        filename = None

        if file and file.filename != "":
            filename = file.filename
            file.save(os.path.join("static/images", filename))

        product = Product(
            name=request.form['name'],
            description=request.form['description'],
            price=float(request.form['price']),
            stock=int(request.form['stock']),
            image=filename
        )

        db.session.add(product)
        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template('add_product.html')
@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():

    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    admin = Admin.query.get(session['admin'])

    if request.method == 'POST':

        admin.username = request.form['username']
        admin.password = generate_password_hash(request.form['password'])

        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template('admin_settings.html', admin=admin)


# ==========================
# UPDATE ORDER STATUS
# ==========================

@app.route('/order/status/<int:order_id>')
def update_order_status(order_id):

    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    order = Order.query.get_or_404(order_id)

    if order.status == 'Pending':
        order.status = 'Completed'
    else:
        order.status = 'Pending'

    db.session.commit()

    return redirect(url_for('dashboard'))


# ==========================
# CREATE DATABASE
# ==========================

if __name__ == '__main__':

    with app.app_context():
        db.create_all()

        admin = Admin.query.filter_by(
            username='admin'
        ).first()

        if not admin:

            admin = Admin(
                username='admin',
                password=generate_password_hash(
                    'admin123'
                )
            )

            db.session.add(admin)
            db.session.commit()

    app.run(debug=True)