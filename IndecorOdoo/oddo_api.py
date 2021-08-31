class OdooInstance:
    def __init__(self, url, db, username, password):
        """url: The URL of Odoo installation.
        db: The database used by Odoo.
        username: The name of the user we want to authenticate as.
        password: The password for the selected user."""
        self.url = url
        self.db = db
        self.username = username
        self.password = password
