from flask_mail import Mail

# Shared Mail instance for the application. Initialize in create_app via
# mail.init_app(app)
mail = Mail()
