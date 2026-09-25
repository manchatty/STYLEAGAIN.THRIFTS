# STYLE AGAIN THRIFTS — Flask Thrift Store

A complete starter thrift-store website with:

- Customer registration/login
- Product catalogue
- Cart and checkout
- Customer order history
- Admin login
- Admin product add/edit/delete
- Admin price and stock editing
- Admin order/customer details
- Order status updates
- SQLite database
- Password hashing
- Responsive streetwear-style UI

## Run locally

1. Open a terminal in this folder.
2. Create a virtual environment (recommended):
   `python -m venv venv`
3. Activate it:
   Windows: `venv\Scripts\activate`
4. Install:
   `pip install -r requirements.txt`
5. Start:
   `python app.py`
6. Open `http://127.0.0.1:5000`

## Admin login

Email: `admin@thrift.local`
Password: `admin123`

Change the default admin password and `SECRET_KEY` before putting the site online.

## How it works

Admin:
`/login` → use the admin account → `/admin`

Customer:
`/register` → create account → shop → add to bag → checkout.

When a customer places an order, the order, delivery address, phone number, products and total are stored in SQLite and appear in the admin dashboard.

## Production notes

Before public deployment, add CSRF protection, rate limiting, email/order notifications, payment gateway integration, image uploads/cloud storage, stronger secret management, HTTPS, and proper database backups.


## Updated features
- STYLE AGAIN THRIFTS branding
- Drag-and-drop product image uploads with preview
- Supplied UPI QR code on checkout
- Product, hover, entrance and payment animations

## Order approval flow
Customers submit an order request after checkout. The order starts as `Pending Approval`. If an admin is logged into the dashboard, a live popup appears for new orders. Only the admin can change the order to `Approved`; stock is deducted when the order is approved. The customer sees a success page and can track the order status.
