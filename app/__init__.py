from flask import Flask
from .call_manager import call_manager
import os

app = Flask(__name__)

# Initialize call manager
call_manager.init_app(app)

# Import routes after app is created
from . import routes