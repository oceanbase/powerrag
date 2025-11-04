#
#  Copyright 2025 The OceanBase Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""PowerRAG Flask Application Configuration"""

import logging
import json
from flask import Flask
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from api.utils.json import CustomJSONEncoder

logger = logging.getLogger(__name__)


class CustomJSONProvider(DefaultJSONProvider):
    """Custom JSON provider that supports Chinese characters without Unicode escaping"""
    
    def dumps(self, obj, **kwargs):
        """Override dumps to ensure Chinese characters are not escaped"""
        kwargs.setdefault('ensure_ascii', False)
        kwargs.setdefault('cls', CustomJSONEncoder)
        return json.dumps(obj, **kwargs)


def create_app():
    """Create and configure the PowerRAG Flask application"""
    
    app = Flask(__name__)
    
    # CORS configuration - allow requests from RAGFlow frontend
    CORS(app, supports_credentials=True, max_age=2592000)
    
    # JSON encoder configuration
    # Use custom JSON provider to ensure Chinese characters are displayed properly
    app.json = CustomJSONProvider(app)
    
    # Request configuration
    app.url_map.strict_slashes = False
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1GB max upload
    
    # Register blueprints
    from powerrag.server.routes.powerrag_routes import powerrag_bp
    from powerrag.server.routes.task_routes import task_bp
    
    app.register_blueprint(powerrag_bp, url_prefix="/api/v1/powerrag")
    app.register_blueprint(task_bp, url_prefix="/api/v1/powerrag")
    
    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health_check():
        return {"status": "ok", "service": "powerrag"}, 200
    
    logger.info("PowerRAG Flask application created successfully")
    
    return app

