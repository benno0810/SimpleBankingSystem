from flask import Flask
from SimpleBankingSystem.api import api_bp
from SimpleBankingSystem.commands import CommandInvoker
import os

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Initialize command invoker
    invoker = CommandInvoker()
    app.invoker = invoker
    
    # Register API blueprint with URL prefix
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Configure app
    app.config['TESTING'] = False
    app.config['DEBUG'] = False
    app.config['ACCOUNTS'] = invoker.accounts
    
    # Handle trailing slashes consistently
    app.url_map.strict_slashes = False
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True) 